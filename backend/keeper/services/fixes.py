"""Fix and test (FR-FIX): start, list, detail, patch download, cancel."""

from __future__ import annotations

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.services import views as V
from keeper.services.common import confirm, estimate, job_ref, project, provenance, pull, require_live


def start_fix(pid: str, n: int, body: S.FixRequest, ctx: Ctx) -> S.JobAccepted:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can start a fix.")
    require_live()
    if not body.finding_ids:
        raise ValidationFailed("Choose at least one finding to fix.")
    with session_scope() as db:
        p = project(db, pid)
        pull(db, p, n)
        for rid in body.finding_ids:
            rf = db.get(M.RoutedFindingRow, rid)
            if rf is None:
                raise NotFound("Finding not found.")
            f = db.get(M.FindingRow, rf.finding_id)
            if not (rf.fixable and get_config().fixable(f.category)):
                raise ValidationFailed("Keeper only proposes text for this kind of finding (build, release and "
                                       "dependency changes need a person).")
    confirm("fix", {"pid": pid, "n": n, "f": sorted(body.finding_ids)}, estimate("fix_run"), body.confirm_token,
            f"Fix and test {len(body.finding_ids)} finding(s) on #{n}")
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("fix", {"project_id": pid, "number": n, "finding_ids": body.finding_ids,
                                                "branches": body.branches, "user_hint": body.user_hint,
                                                "both_ways": body.both_ways},
                                        key=f"fix:{pid}:{n}:{','.join(sorted(body.finding_ids))}")
    return job_ref(jid, "fix", existing)


def _summary(r: M.FixRun) -> S.FixRunSummary:
    return S.FixRunSummary(id=r.id, status=r.status, finding_ids=r.finding_ids or [], provider=r.provider,
                           winning_branch=r.winning_branch, iterations=r.iterations, diff_stats=r.diff_stats or {},
                           junit_summary=r.junit_summary or {}, created_at=r.created_at, finished_at=r.finished_at,
                           job_id=r.job_id, provenance=provenance(r.origin, r.finished_at or r.created_at, None, None,
                                                                  list(r.models or [])))


def list_fixes(pid: str, n: int) -> S.FixRunList:
    with session_scope() as db:
        p = project(db, pid)
        rows = db.execute(select(M.FixRun).where(M.FixRun.project_id == p.id, M.FixRun.pr_number == n)
                          .order_by(M.FixRun.created_at.desc())).scalars().all()
        rows.sort(key=lambda r: (r.origin != "live", -(r.created_at.timestamp())))
        return S.FixRunList(items=[_summary(r) for r in rows])


def _test(t: dict | None) -> S.TestResult | None:  # type: ignore[type-arg]
    if not t:
        return None
    return S.TestResult(passed=t.get("passed", 0), failed=t.get("failed", 0), skipped=t.get("skipped", 0),
                        errors=t.get("errors", 0), duration_ms=t.get("duration_ms", 0),
                        failures=[S.TestFailure(**f) for f in t.get("failures", [])], lint_errors=t.get("lint_errors", 0),
                        ok=bool(t.get("ok")))


def get_fix(fix_id: str) -> S.FixRunDetail:
    with session_scope() as db:
        r = db.get(M.FixRun, fix_id)
        if r is None:
            raise NotFound("Fix run not found.")
        attempts = db.execute(select(M.FixAttempt).where(M.FixAttempt.fix_run_id == r.id)
                              .order_by(M.FixAttempt.branch, M.FixAttempt.iteration)).scalars().all()
        branches: dict[str, S.FixBranchOut] = {}
        for a in attempts:
            tr = dict(a.test_result or {})
            b = branches.setdefault(a.branch, S.FixBranchOut(name=a.branch, status=tr.get("branch_status", "failed"),
                                                              approach=a.plan_md, attempts=[]))
            b.attempts.append(S.FixAttemptOut(iteration=a.iteration, step=a.step, plan_md=a.plan_md, edits=a.edits or [],
                                              apply_errors=a.apply_errors or [], test=_test({k: v for k, v in tr.items()
                                                                                              if k not in ("verify",)})
                                              if tr.get("passed") is not None or tr.get("failed") is not None else None,
                                              verify=tr.get("verify"), model=S.ModelTag(display=a.model, latency_ms=a.latency_ms),
                                              started_at=a.started_at, finished_at=a.finished_at))
            if tr.get("diff"):
                b.diff = tr["diff"]
        if r.winning_branch in branches:
            branches[r.winning_branch].diff = r.diff
            branches[r.winning_branch].diff_stats = r.diff_stats or {}
        from keeper.sandbox.select import last_selection
        findings = []
        if r.analysis_id:
            a = db.get(M.Analysis, r.analysis_id)
            items = V.items_of(db, a.lens_version_id) if a else {}
            for rid in r.finding_ids or []:
                rf = db.get(M.RoutedFindingRow, rid)
                if rf and a and (o := V.routed_out(db, a, rf, items)):
                    findings.append(o)
        base = (r.junit_summary or {}).get("baseline") or {}
        sug = _suggestion(r.diff) if r.diff else None
        isolation = {"local": (last_selection() or {}).get("isolation") or "Local sandbox: tests run on this machine "
                     "with limited isolation.", "docker": "Docker: no network, 2 CPUs, 2 GB of memory."}.get(r.provider or "")
        return S.FixRunDetail(**_summary(r).model_dump(), pr_number=r.pr_number, provider_reason=r.provider_reason,
                              isolation=isolation, baseline_tests=S.TestResult(passed=base.get("passed", 0),
                                                                               failed=base.get("failed", 0),
                                                                               skipped=base.get("skipped", 0),
                                                                               duration_ms=int(base.get("time", 0) * 1000),
                                                                               ok=not base.get("failed")) if base else None,
                              baseline_failures=r.baseline_failures or [], branches=list(branches.values()),
                              diff=r.diff, cost_usd=r.cost_usd or 0, error=r.error, suggestion_md=sug, findings=findings)


def _suggestion(diff: str) -> str | None:
    """A GitHub suggestion block for single-hunk, single-file changes; otherwise None (use the patch)."""
    files = [ln for ln in diff.split("\n") if ln.startswith("+++ ")]
    hunks = [ln for ln in diff.split("\n") if ln.startswith("@@")]
    if len(files) != 1 or len(hunks) != 1:
        return None
    new = [ln[1:] for ln in diff.split("\n") if ln.startswith("+") and not ln.startswith("+++")]
    return "```suggestion\n" + "\n".join(new) + "\n```"


def get_patch(fix_id: str) -> tuple[str, str]:
    with session_scope() as db:
        r = db.get(M.FixRun, fix_id)
        if r is None or not r.diff:
            raise NotFound("This fix run has no passing diff.")
        author = get_config().review["patch_author"]
        body = (f"From: {author}\nSubject: [PATCH] Suggested fix for #{r.pr_number} (drafted by Keeper; not pushed)\n\n"
                f"---\n{r.diff}")
        return f"keeper-fix-{r.pr_number}-{r.id[-6:]}.patch", body


def cancel_fix(fix_id: str, ctx: Ctx) -> S.JobOut:
    from keeper.services import jobs
    with session_scope() as db:
        r = db.get(M.FixRun, fix_id)
        if r is None or not r.job_id:
            raise Conflict("This fix run is not running.")
        job_id = r.job_id
    return jobs.cancel(job_id)

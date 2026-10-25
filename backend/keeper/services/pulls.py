"""The pull-request view (FR-REV, FR-FB, FR-OUT): header, diff, analysis, compare, history, feedback, review draft,
hand-off and outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from keeper.analysis.context import pr_files
from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import Forbidden, NotFound, ValidationFailed
from keeper.db import models as M
from keeper.db import repo as R
from keeper.db.session import session_scope
from keeper.ids import new_id, stable_id
from keeper.review import export as EXP
from keeper.route.lanes import override_allowed
from keeper.services import views as V
from keeper.services.common import (
    confirm,
    current_version,
    estimate,
    html_url,
    job_ref,
    lens_of,
    maintainer,
    name_of,
    person_ref,
    prefer_live,
    project,
    provenance,
    pull,
    require_live,
)

LARGE = 3000


def _author(db, pr: M.Pull) -> S.AuthorRef:  # type: ignore[no-untyped-def]
    au = db.get(M.Person, pr.author_id) if pr.author_id else None
    return S.AuthorRef(id=au.id if au else None, login=au.login if au else "?", display_name=au.display_name if au else None,
                       association=pr.author_association,
                       first_time=pr.author_association in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"))


def get_pull(pid: str, n: int) -> S.PullDetail:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        files = db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id).order_by(M.PullFile.filename)).scalars()
        checks = db.execute(select(M.CheckRun).where(M.CheckRun.project_id == p.id, M.CheckRun.head_sha == pr.head_sha)
                            ).scalars().all()
        commits = len([c for c in db.execute(select(M.Commit).where(M.Commit.project_id == p.id)).scalars()
                       if n in (c.pull_numbers or [])])
        maint = maintainer(db, p)
        has_human = bool(R.findings(db, p.id, pr_number=n, source="human", person_id=maint.id, context="history"))
        return S.PullDetail(number=pr.number, title=pr.title, body_md=pr.body or "", author=_author(db, pr),
                            state=pr.state, merged=pr.merged_at is not None, labels=pr.labels or [],
                            base=pr.base_ref or "main", head=pr.head_ref or "", head_sha=pr.head_sha,
                            created_at=pr.created_at, closed_at=pr.closed_at, merged_at=pr.merged_at,
                            files=[S.PullFileInfo(filename=f.filename, status=f.status, additions=f.additions,
                                                  deletions=f.deletions, binary=f.binary) for f in files],
                            checks=[S.CheckInfo(name=c.name, conclusion=c.conclusion, summary=c.summary) for c in checks],
                            additions=pr.additions, deletions=pr.deletions, commits=commits,
                            html_url=html_url(p, f"pull/{n}"), split=pr.split,
                            has_human_review=has_human and pr.split != "live")


def get_diff(pid: str, n: int, file: str | None, head_sha: str | None = None) -> S.DiffResponse:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        out = []
        for f in pr_files(db, p, pr, head_sha):
            if file and f.path != file:
                continue
            too_large = bool(f.patch and f.patch.count("\n") > LARGE)
            out.append(S.DiffFile(filename=f.path, status=f.status, patch=f.patch, binary=f.binary, too_large=too_large))
        return S.DiffResponse(files=out)


def _analysis(db, p: M.Project, pr: M.Pull) -> M.Analysis | None:  # type: ignore[no-untyped-def]
    return V.current_analysis(db, p.id, pr, ("queue", "history"))


def get_analysis(pid: str, n: int, ctx: Ctx) -> S.AnalysisResponse:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        a = _analysis(db, p, pr)
        if a is None:
            raise NotFound("Keeper hasn't analysed this PR yet.", {"reason": "no_analysis"})
        items = V.items_of(db, a.lens_version_id)
        rfs = db.execute(select(M.RoutedFindingRow).where(M.RoutedFindingRow.analysis_id == a.id)).scalars().all()
        order = {"edge": 0, "blind_spot": 1, "shared": 2, "baseline_only": 3}
        sev = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}
        outs = [o for r in rfs if (o := V.routed_out(db, a, r, items))]
        outs.sort(key=lambda o: (order.get(o.lane, 9), sev.get(o.severity, 9), o.anchor.path or "", o.anchor.start_line or 0))
        lv = db.get(M.LensVersion, a.lens_version_id) if a.lens_version_id else None
        slop = (a.stats or {}).get("slop", {})
        return S.AnalysisResponse(
            analysis_id=a.id, pr_number=n, lane=V.effective_lane(db, p.id, a), summary_md=a.summary,
            attention_minutes=a.attention_minutes, signals=V.signal_refs(a), reasons=[S.Reason(**r) for r in a.reasons or []],
            slop=S.SlopInfo(score=float(slop.get("score", 0)), label="Looks auto-generated" if slop.get("is_slop") else None,
                            evidence=slop.get("evidence", [])) if slop else None,
            recall_mode=a.recall_mode, findings=[o for o in outs if o.lane != "baseline_only"] +
            [o for o in outs if o.lane == "baseline_only"], baseline_only_count=sum(1 for o in outs if o.lane == "baseline_only"),
            stats={k: v for k, v in (a.stats or {}).items() if k not in ("model_meta",)}, lens_version=lv.version if lv else None,
            lens_paused=bool((a.stats or {}).get("lens_paused")),
            baseline_unavailable=bool((a.stats or {}).get("baseline_unavailable")), provenance=V.analysis_provenance(db, a))


def analyze(pid: str, n: int, body: S.AnalyzeRequest, ctx: Ctx) -> S.JobAccepted:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can re-run an analysis.")
    require_live()
    confirm("analyze", {"pid": pid, "n": n}, estimate("analyze_pr"), body.confirm_token, f"Analyse PR #{n} again")
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("analyze", {"project_id": pid, "number": n}, key=f"analyze:{pid}:{n}")
    return job_ref(jid, "analyze", existing)


def get_compare(pid: str, n: int) -> S.CompareResponse:
    """Live PRs: the queue analysis. Held-out PRs: the latest Proof case, with what the maintainer actually wrote."""
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        maint = maintainer(db, p)
        login = maint.login
        a = _analysis(db, p, pr)
        if a is not None and (pr.split == "live" or not _fidelity_case(db, p, n)):
            lens = [f for f in db.execute(select(M.FindingRow).where(
                M.FindingRow.project_id == p.id, M.FindingRow.pr_number == n, M.FindingRow.source == "lens",
                M.FindingRow.lens_version_id == a.lens_version_id, M.FindingRow.head_sha == a.head_sha,
                M.FindingRow.context == a.purpose)).scalars()]
            base = [f for f in db.execute(select(M.FindingRow).where(
                M.FindingRow.project_id == p.id, M.FindingRow.pr_number == n, M.FindingRow.source == "baseline",
                M.FindingRow.head_sha == a.head_sha, M.FindingRow.ruler_id == a.ruler_id)).scalars()]
            pairs = [S.ComparePair(baseline_id=m.b_id, lens_id=m.a_id, decision=m.decision, rationale=m.rationale)
                     for m in db.execute(select(M.FindingMatch).where(M.FindingMatch.project_id == p.id,
                                                                      M.FindingMatch.pr_number == n,
                                                                      M.FindingMatch.set_a == f"lens:{a.purpose}",
                                                                      M.FindingMatch.assigned.is_(True))).scalars()]
            human, hp = _human(db, p, pr, maint, lens, base, None)
            prov = V.analysis_provenance(db, a)
        else:
            case_run = _fidelity_case(db, p, n)
            if case_run is None:
                raise NotFound("Not in the saved results.", {"reason": "no_analysis"})
            case, run = case_run
            ps = case.per_system
            lens = [f for fid in ps["lens"]["ids"] if (f := db.get(M.FindingRow, fid))]
            base = [f for fid in ps["baseline"]["ids"] if (f := db.get(M.FindingRow, fid))]
            pairs = [S.ComparePair(baseline_id=x["baseline_id"], lens_id=x["lens_id"], decision=x["decision"])
                     for x in ps.get("lens_baseline_pairs", [])]
            human, hp = _human(db, p, pr, maint, lens, base, ps)
            lv = db.get(M.LensVersion, run.lens_version_id)
            prov = provenance(run.origin, run.created_at, run.ruler_id, lv.version if lv else None, list(run.models or []))
        r_plus = [f.id for f in lens if f.id not in {x.lens_id for x in pairs}]
        r_minus = [f.id for f in base if f.id not in {x.baseline_id for x in pairs}]
        counts = {"baseline": len(base), "lens": len(lens), "edge": len(r_plus), "shared": len(pairs),
                  "blind": 0, "human": len(human or [])}
        return S.CompareResponse(pr_number=n, baseline=[V.finding_out(db, f) for f in base],
                                 lens=[V.finding_out(db, f, login) for f in lens], pairs=pairs,
                                 residual=S.CompareResidual(r_plus=r_plus, r_minus=r_minus),
                                 human=human, human_pairs=hp, maintainer=person_ref(maint), counts=counts, provenance=prov)


def _fidelity_case(db, p: M.Project, n: int):  # type: ignore[no-untyped-def]
    runs = db.execute(select(M.FidelityRun).where(M.FidelityRun.project_id == p.id)).scalars().all()
    run = prefer_live(runs)
    if run is None:
        return None
    case = db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == run.id, M.FidelityCase.pr_number == n)
                      ).scalars().first()
    return (case, run) if case else None


def _human(db, p, pr, maint, lens, base, ps):  # type: ignore[no-untyped-def]
    if pr.split == "live":
        return None, []
    hs = [db.get(M.FindingRow, f.id) for f in R.findings(db, p.id, pr_number=pr.number, source="human",
                                                         person_id=maint.id, context="history") if f.substantive]
    pairs: list[S.HumanPair] = []
    if ps is not None:
        for sysname in ("lens", "baseline"):
            for x in ps[sysname].get("pairs", []):
                pairs.append(S.HumanPair(human_id=x["human_id"], other_id=x["other_id"], system=sysname,
                                         decision=x["decision"]))
    return [V.finding_out(db, f, maint.login) for f in hs if f], pairs


def get_history(pid: str, n: int, person_id: str | None) -> S.HistoryResponse:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        person = person_id or maintainer(db, p).id
        files = {f.filename for f in db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id)).scalars()}
        dirs = {f.rsplit("/", 1)[0] for f in files}
        out = []
        for f in R.findings(db, p.id, source="human", person_id=person, context="history"):
            if f.pr_number == n or not f.anchor.path or (f.created_at and pr.created_at and f.created_at >= pr.created_at):
                continue
            if f.anchor.path in files or f.anchor.path.rsplit("/", 1)[0] in dirs:
                pc = V.past_comment(db, f.id)
                out.append(S.HistoryItem(comment_id=f.id, pr_number=f.pr_number, path=f.anchor.path, excerpt=pc.excerpt
                                         if pc else f.statement, at=f.created_at, html_url=pc.html_url if pc else None,
                                         category=f.category))
        out.sort(key=lambda x: x.at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return S.HistoryResponse(items=out[:20])


def get_human_review(pid: str, n: int) -> S.HumanReviewResponse:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        if pr.split == "live":
            raise Forbidden("The maintainer hasn't reviewed this open PR; Keeper never shows reviews of live PRs here.")
        maint = maintainer(db, p)
        comments = []
        for c in db.execute(select(M.ReviewComment).where(M.ReviewComment.pull_id == pr.id,
                                                          M.ReviewComment.author_id == maint.id)
                            .order_by(M.ReviewComment.created_at)).scalars():
            comments.append(S.HumanReviewComment(id=str(c.gh_id), kind="review_comment", path=c.path,
                                                 line=c.original_line or c.line, body_md=c.body, author=maint.login,
                                                 at=c.created_at, html_url=c.html_url))
        for r in db.execute(select(M.Review).where(M.Review.pull_id == pr.id, M.Review.reviewer_id == maint.id)).scalars():
            if r.body:
                comments.append(S.HumanReviewComment(id=str(r.gh_id), kind="review", body_md=r.body, author=maint.login,
                                                     at=r.submitted_at, html_url=r.html_url))
        fs = [db.get(M.FindingRow, f.id) for f in R.findings(db, p.id, pr_number=n, source="human", person_id=maint.id,
                                                             context="history")]
        return S.HumanReviewResponse(pr_number=n, person=person_ref(maint), comments=comments,
                                     findings=[V.finding_out(db, f, maint.login) for f in fs if f])


def patch_finding(pid: str, rf_id: str, body: S.FeedbackRequest, ctx: Ctx) -> S.RoutedFindingOut:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can give feedback on Keeper's notes.")
    with session_scope() as db:
        p = project(db, pid)
        rf = db.get(M.RoutedFindingRow, rf_id)
        if rf is None:
            raise NotFound("Finding not found.")
        a = db.get(M.Analysis, rf.analysis_id)
        if body.state == "good_catch" and rf.lane != "blind_spot":
            raise ValidationFailed("Good catch is for notes in Worth a second look.")
        rf.user_state = body.state
        if body.state == "edited":
            rf.user_text = (body.text or "").strip() or rf.user_text
            if body.severity:
                rf.user_severity = body.severity
        if body.state == "open":
            rf.user_text, rf.user_severity = None, None
        kind = {"accepted": "accept", "edited": "edit", "dismissed": "dismiss", "good_catch": "good_catch",
                "open": "undo"}[body.state]
        db.add(M.FeedbackEvent(id=new_id("fb"), project_id=p.id, pr_number=a.pr_number, routed_finding_id=rf.id, kind=kind,
                               payload={"text": body.text, "severity": body.severity, "reason": body.reason},
                               lens_version_id=a.lens_version_id, ruler_id=a.ruler_id))
        if body.state == "good_catch":
            rf.fixable = get_config().fixable(db.get(M.FindingRow, rf.finding_id).category)
        db.flush()
        return V.routed_out(db, a, rf, V.items_of(db, a.lens_version_id))


def add_note(pid: str, n: int, body: S.NoteRequest, ctx: Ctx) -> S.RoutedFindingOut:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can add notes.")
    if not body.text.strip():
        raise ValidationFailed("Write the note first.")
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        a = _analysis(db, p, pr)
        if a is None:
            raise NotFound("Keeper hasn't analysed this PR yet.")
        maint = maintainer(db, p)
        cat = body.category if body.category in get_config().taxonomy["categories"] else "correctness"
        fid = stable_id("fnd", p.id, n, "note", new_id("x"))
        db.add(M.FindingRow(id=fid, project_id=p.id, pr_number=n, head_sha=a.head_sha, source="human",
                            person_id=maint.id, scope="line" if body.path and body.line else ("file" if body.path else "pr"),
                            path=body.path, start_line=body.line, end_line=body.line, category=cat, severity="minor",
                            kind="comment", statement=body.text.strip(), substantive=get_config().substantive(cat),
                            refs={"added_note": True}, context="feedback", created_at=datetime.now(UTC)))
        rf = M.RoutedFindingRow(id=stable_id("rf", a.id, fid), analysis_id=a.id, finding_id=fid, lane="edge",
                                action="draft_and_offer_fix", fixable=get_config().fixable(cat), evidence={"added_note": True},
                                user_state="accepted")
        db.add(rf)
        db.add(M.FeedbackEvent(id=new_id("fb"), project_id=p.id, pr_number=n, routed_finding_id=rf.id, kind="add_note",
                               payload={"text": body.text, "path": body.path, "line": body.line},
                               lens_version_id=a.lens_version_id, ruler_id=a.ruler_id))
        db.flush()
        return V.routed_out(db, a, rf, V.items_of(db, a.lens_version_id))


def override_lane(pid: str, n: int, body: S.LaneOverrideRequest, ctx: Ctx) -> S.LaneOverrideResponse:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        a = _analysis(db, p, pr)
        if a is None:
            raise NotFound("Keeper hasn't analysed this PR yet.")
        cur = V.effective_lane(db, p.id, a)
        ok, why = override_allowed(cur, body.lane, V.signals_of(a), owner=ctx.role == "maintainer")
        if not ok:
            msg = ("Keeper never lowers attention on build, release or binary changes. You can hand it to yourself "
                   "instead." if why == "risk_signal" else "Only the maintainer can lower a PR's lane.")
            return S.LaneOverrideResponse(lane=cur, blocked=True, message=msg)
        db.add(M.FeedbackEvent(id=new_id("fb"), project_id=p.id, pr_number=n, kind="lane_override",
                               payload={"lane": body.lane, "from": cur, "reason": body.reason},
                               lens_version_id=a.lens_version_id, ruler_id=a.ruler_id))
        R.audit(db, ctx.role, "lane_override", "pull", str(n), {"from": cur, "to": body.lane})
        return S.LaneOverrideResponse(lane=body.lane, blocked=False)


def _draft_row(db, p, pr):  # type: ignore[no-untyped-def]
    a = _analysis(db, p, pr)
    if a is None:
        raise NotFound("Keeper hasn't analysed this PR yet.")
    rows = db.execute(select(M.ReviewDraft).where(M.ReviewDraft.analysis_id == a.id)).scalars().all()
    d = prefer_live(rows) if rows else None
    if d is None:
        raise NotFound("No review draft yet.")
    return a, d


def _labels(db, p, a) -> tuple[str, str]:  # type: ignore[no-untyped-def]
    maint = maintainer(db, p)
    lv = db.get(M.LensVersion, a.lens_version_id) if a.lens_version_id else None
    rc = get_config().review
    return (rc["label_line"].format(maintainer=name_of(maint)),
            rc["draft_header"].format(maintainer=name_of(maint), version=lv.version if lv else "?"))


def get_review_draft(pid: str, n: int) -> S.ReviewDraftOut:
    with session_scope() as db:
        p = project(db, pid)
        a, d = _draft_row(db, p, pull(db, p, n))
        label, header = _labels(db, p, a)
        return S.ReviewDraftOut(body_md=d.body_md, comments=[S.DraftComment(**c) for c in d.comments or []],
                                event=d.event if d.event in ("COMMENT", "REQUEST_CHANGES", "APPROVE") else "COMMENT",
                                edited_by_user=d.edited_by_user, label=label, header=header, updated_at=d.updated_at,
                                provenance=provenance(d.origin, d.updated_at, a.ruler_id, None, list(d.models or [])))


def put_review_draft(pid: str, n: int, body: S.ReviewDraftUpdate, ctx: Ctx) -> S.ReviewDraftOut:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can edit the review draft.")
    with session_scope() as db:
        p = project(db, pid)
        a, d = _draft_row(db, p, pull(db, p, n))
        if d.origin == "snapshot":  # edits create a live copy; the saved one stays as it was
            d = M.ReviewDraft(id=new_id("rd"), analysis_id=a.id, event=d.event, models=d.models, origin="live")
            db.add(d)
        d.body_md, d.comments = body.body_md, [c.model_dump() for c in body.comments]
        d.edited_by_user, d.updated_at = True, datetime.now(UTC)
    return get_review_draft(pid, n)


def export_review_draft(pid: str, n: int, fmt: str) -> S.ReviewDraftExport:
    with session_scope() as db:
        p = project(db, pid)
        a, d = _draft_row(db, p, pull(db, p, n))
        label, header = _labels(db, p, a)
        draft = {"body_md": d.body_md, "comments": d.comments or [], "event": d.event}
        if fmt == "github_json":
            return S.ReviewDraftExport(format="github_json", content=EXP.github_json(draft, label),
                                       filename=f"review-{n}.json", gh_command=EXP.gh_command(p.owner, p.repo, n))
        return S.ReviewDraftExport(format="md", content=EXP.markdown(draft, label, header), filename=f"review-{n}.md")


def start_handoff(pid: str, n: int, body: S.ActionRequest, ctx: Ctx) -> S.JobAccepted:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can request a hand-off.")
    require_live()
    confirm("handoff", {"pid": pid, "n": n}, estimate("handoff"), body.confirm_token, f"Draft a hand-off for #{n}")
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("handoff", {"project_id": pid, "number": n}, key=f"handoff:{pid}:{n}")
    return job_ref(jid, "handoff", existing)


def get_handoff(pid: str, n: int) -> S.HandoffOut:
    with session_scope() as db:
        p = project(db, pid)
        pr = pull(db, p, n)
        a = _analysis(db, p, pr)
        if a is None:
            raise NotFound("Keeper hasn't analysed this PR yet.")
        rows = db.execute(select(M.Handoff).where(M.Handoff.analysis_id == a.id)).scalars().all()
        h = prefer_live(rows)
        if h is None:
            raise NotFound("No hand-off yet.")
        cands = []
        for c in h.candidates or []:
            pe = db.get(M.Person, c["person_id"])
            if pe:
                cands.append(S.HandoffCandidate(person=person_ref(pe), score=c["score"], competence=c["competence"],
                                                distance=c.get("distance"), why=c.get("why", [])))
        target = db.get(M.Person, h.target_person_id) if h.target_person_id else None
        osv = []
        for o in (h.osv or {}).get("packages", []):
            osv.append(S.OsvPackage(name=o["name"], version=o.get("version"), error=o.get("error"),
                                    vulns=[S.OsvVuln(**v) for v in o.get("vulns", [])]))
        tav = h.tavily or {}
        cfg = get_config()
        msg = None if cands else "No one in this project's history covers this. Consider asking a security reviewer."
        return S.HandoffOut(candidates=cands, target=person_ref(target), note_md=h.note_md, checklist=h.checklist or [],
                            signals=V.signal_refs(a), osv=osv,
                            osv_status="checked" if osv else "not_needed",
                            tavily=[S.TavilyResult(**r) for r in tav.get("results", [])],
                            tavily_status=tav.get("status", "not_configured"), no_candidate_message=msg,
                            model=S.ModelTag(model_id=(h.models or [None])[0], display=cfg.model_display((h.models or [""])[0]))
                            if h.models else None,
                            provenance=provenance(h.origin, h.created_at, a.ruler_id, None, list(h.models or [])))


def get_outcomes(pid: str, n: int) -> S.OutcomesResponse:
    with session_scope() as db:
        p = project(db, pid)
        pull(db, p, n)
        rows = db.execute(select(M.Outcome).where(M.Outcome.project_id == p.id, M.Outcome.pr_number == n)).scalars().all()
        return S.OutcomesResponse(items=[S.OutcomeOut(kind=o.kind, at=o.at, evidence={k: v for k, v in (o.evidence or {}).items()
                                                                                       if k != "touched"}) for o in rows])


_ = (Any, lens_of, current_version)

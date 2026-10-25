"""Proof: the Perspective Fidelity Test (FR-FID): runs, detail, cases, start."""

from __future__ import annotations

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import Forbidden, NotFound
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.services import views as V
from keeper.services.common import (
    confirm,
    current_version,
    estimate,
    job_ref,
    lens_of,
    maintainer,
    name_of,
    person_ref,
    project,
    provenance,
    require_live,
)

FALSIFIER_TEXT = {
    "residual_noise": ("The residual predicts something", "If what the maintainer notices beyond generic review were "
                       "just noise, the lens couldn't recover any of it on new PRs."),
    "no_transfer": ("The lens beats generic review on unseen PRs", "If lenses don't transfer, the lens would do no "
                    "better than generic review on PRs it never saw."),
    "caricature": ("No exaggeration of {name}'s favourite concerns", "A caricature flags someone's most typical concerns "
                   "far more often than they do."),
    "just_preference": ("Perspective is just preference", "Not tested in this version: it needs comparing outcomes "
                        "across reviewers with different lenses."),
    "shrinks_people": ("{name}'s own edge is holding", "If AI shrinks the people it learns from, their R+ per PR would "
                       "fall while its hit rate holds."),
    "help_hollows": ("Practice doesn't make learners worse unassisted", "If help hollows, learners would score lower "
                     "on the after check than before, without the tool."),
    "contrarians": ("Edge growing without losing accuracy", "If the loop grows contrarians, R+ would rise while its "
                    "hit rate falls."),
    "loses_value": ("Perspective loses value as AI improves", "Not tested in this version: it needs several model "
                    "generations."),
}
CRITERIA = {"recall_beats_baseline": "Keeper recovers more than generic review (interval above zero)",
            "noise_not_worse": "No more noise per PR than generic review",
            "no_caricature": "No exaggeration (top-category ratio ≤ {max_ratio}, category spread no worse)",
            "unknown_lane_recall": "Every risky PR goes to another reviewer (demo only)"}


def list_runs(pid: str) -> S.FidelityRunList:
    with session_scope() as db:
        p = project(db, pid)
        runs = db.execute(select(M.FidelityRun).where(M.FidelityRun.project_id == p.id)
                          .order_by(M.FidelityRun.created_at.desc())).scalars().all()
        runs.sort(key=lambda r: (r.origin != "live", -r.created_at.timestamp()))
        out = []
        for r in runs:
            lv = db.get(M.LensVersion, r.lens_version_id)
            out.append(S.FidelityRunRef(id=r.id, lens_version=lv.version if lv else 0, created_at=r.created_at,
                                        pass_overall=bool((r.passes or {}).get("overall")), origin=r.origin,
                                        prs=int((r.holdout_spec or {}).get("prs", 0)),
                                        simulated=provenance(r.origin, r.created_at, models=list(r.models or [])).simulated))
        return S.FidelityRunList(items=out)


def _metric(d: dict | None) -> S.Metric:  # type: ignore[type-arg]
    d = d or {}
    return S.Metric(value=d.get("value"), low=d.get("low"), high=d.get("high"), n=d.get("n"))


def get_run(fid: str) -> S.FidelityRunOut:
    cfg = get_config()
    with session_scope() as db:
        r = db.get(M.FidelityRun, fid)
        if r is None:
            raise NotFound("Proof run not found.")
        pe = db.get(M.Person, r.person_id)
        lv = db.get(M.LensVersion, r.lens_version_id)
        name = name_of(pe)
        metrics = {}
        for s, m in (r.metrics or {}).items():
            metrics[s] = S.SystemMetrics(substantive_recall=_metric(m.get("substantive_recall")),
                                         residual_recall=_metric(m.get("residual_recall")),
                                         noise_per_pr=_metric(m.get("noise_per_pr")), precision=_metric(m.get("precision")),
                                         caricature_ratio=_metric(m.get("caricature_ratio")), jsd=_metric(m.get("jsd")),
                                         per_category=m.get("per_category", {}))
        diff = (r.ci or {}).get("paired_difference", {})
        passes = r.passes or {}
        k, b, lens = (r.metrics or {}).get("keeper", {}), (r.metrics or {}).get("baseline", {}), (r.metrics or {}).get("lens", {})

        def pct(x: float | None) -> str:
            return "—" if x is None else f"{x * 100:.0f}%"
        details = {"recall_beats_baseline": f"Keeper {pct(k.get('substantive_recall', {}).get('value'))} vs generic "
                   f"{pct(b.get('substantive_recall', {}).get('value'))}; difference {pct(diff.get('value'))} "
                   f"({pct(diff.get('low'))} to {pct(diff.get('high'))})",
                   "noise_not_worse": f"Keeper {k.get('noise_per_pr', {}).get('value') or 0:.2f} vs generic "
                   f"{b.get('noise_per_pr', {}).get('value') or 0:.2f} per PR",
                   "no_caricature": f"max ratio {lens.get('caricature_ratio', {}).get('value') or 0:.2f}; spread "
                   f"{lens.get('jsd', {}).get('value') or 0:.2f} vs generic {b.get('jsd', {}).get('value') or 0:.2f}",
                   "unknown_lane_recall": f"{(r.measurement or {}).get('routing', {}).get('unknown_recall', '—')}"}
        criteria = [S.Criterion(key=key, label=CRITERIA[key].format(max_ratio=cfg.fidelity["caricature"]["max_ratio"]),
                                passed=passes.get(key), detail=details.get(key, "")) for key in CRITERIA if key in passes]
        fals = [S.Falsifier(key=f["key"], name=FALSIFIER_TEXT[f["key"]][0].format(name=name),
                            description_md=FALSIFIER_TEXT[f["key"]][1], result=f["result"], passed=f["passed"])
                for f in (r.falsifiers or []) if f["key"] in FALSIFIER_TEXT]
        return S.FidelityRunOut(id=r.id, lens_version=lv.version if lv else 0, person=person_ref(pe),
                                holdout=r.holdout_spec or {}, metrics=metrics, paired_difference=_metric(diff),
                                p_value=diff.get("p"), routing=(r.measurement or {}).get("routing", {}), criteria=criteria,
                                pass_overall=bool(passes.get("overall")), falsifiers=fals, sensitivity=r.sensitivity or {},
                                measurement={k2: v for k2, v in (r.measurement or {}).items() if k2 != "lanes"},
                                cases_count=int((r.holdout_spec or {}).get("prs", 0)), cost_usd=r.cost_usd or 0,
                                created_at=r.created_at,
                                provenance=provenance(r.origin, r.created_at, r.ruler_id, lv.version if lv else None,
                                                      list(r.models or [])))


def list_cases(fid: str, q: str | None, outcome: str | None) -> S.CaseList:
    with session_scope() as db:
        r = db.get(M.FidelityRun, fid)
        if r is None:
            raise NotFound("Proof run not found.")
        out = []
        for c in db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == fid).order_by(M.FidelityCase.pr_number)).scalars():
            pr = db.execute(select(M.Pull).where(M.Pull.project_id == r.project_id, M.Pull.number == c.pr_number)).scalars().first()
            ps = c.per_system
            nh = len(ps.get("h", []))
            lm, bm, km = ps["lens"]["matched_w"], ps["baseline"]["matched_w"], ps["keeper"]["matched_w"]
            kind = "caught" if lm > bm else ("missed" if lm < nh else "extra" if ps["lens"]["noise"] else "caught")
            row = S.CaseRow(pr_number=c.pr_number, title=pr.title if pr else "", maintainer_findings=nh, baseline_matched=bm,
                            lens_matched=lm, keeper_matched=km, lens_extra=ps["lens"]["noise"], outcome=kind)
            if q and q.lower() not in row.title.lower() and q.lstrip("#") != str(row.pr_number):
                continue
            if outcome and outcome != kind:
                continue
            out.append(row)
        return S.CaseList(items=out)


def get_case(fid: str, n: int) -> S.CaseDetail:
    with session_scope() as db:
        r = db.get(M.FidelityRun, fid)
        c = db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == fid, M.FidelityCase.pr_number == n)
                       ).scalars().first() if r else None
        if c is None:
            raise NotFound("Case not found.")
        pe = db.get(M.Person, r.person_id)
        pr = db.execute(select(M.Pull).where(M.Pull.project_id == r.project_id, M.Pull.number == n)).scalars().first()
        ps = c.per_system

        def fs(ids):  # type: ignore[no-untyped-def]
            return [V.finding_out(db, f, pe.login if f.source in ("human", "lens") else None)
                    for i in ids if (f := db.get(M.FindingRow, i))]
        matches = [S.HumanPair(human_id=x["human_id"], other_id=x["other_id"], system=s, decision=x["decision"])
                   for s in ("lens", "baseline") for x in ps[s].get("pairs", [])]
        return S.CaseDetail(pr_number=n, title=pr.title if pr else "", human=fs(ps["h"]), baseline=fs(ps["baseline"]["ids"]),
                            lens=fs(ps["lens"]["ids"]), matches=matches,
                            lens_baseline_pairs=[S.ComparePair(baseline_id=x["baseline_id"], lens_id=x["lens_id"],
                                                               decision=x["decision"]) for x in ps.get("lens_baseline_pairs", [])])


def start_run(pid: str, body: S.FidelityRunRequest, ctx: Ctx) -> S.JobAccepted:
    if ctx.role not in ("maintainer", "judge"):
        raise Forbidden("Only the maintainer can run Proof.")
    require_live()
    with session_scope() as db:
        p = project(db, pid)
        lens = lens_of(db, p, maintainer(db, p).id)
        if lens is None:
            raise NotFound("Build a lens first.")
        lv = current_version(db, lens)
        version = body.lens_version or (1 if lv and lv.version > 1 else (lv.version if lv else 1))
        n = int((db.execute(select(M.FidelityRun).where(M.FidelityRun.project_id == p.id)).scalars().first() or
                 M.FidelityRun(holdout_spec={"prs": 30})).holdout_spec.get("prs", 30))
    confirm("fidelity", {"pid": pid, "v": version}, estimate("fidelity_per_pr", n), body.confirm_token,
            f"Run the Fidelity Test on {n} held-out PRs")
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("fidelity", {"project_id": pid, "lens_version": version,
                                                     "use_batch": body.use_batch}, key=f"fidelity:{pid}")
    return job_ref(jid, "fidelity", existing)

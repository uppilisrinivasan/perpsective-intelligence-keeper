"""The guided tour (docs/06-frontend/04 §3): steps chosen from data. A step whose target is missing is dropped."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.config import get_config, get_settings
from keeper.core.errors import NotFound
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.services.common import maintainer, name_of, prefer_live, project


def _manifest_hints() -> dict[str, Any]:
    import json
    f = get_settings().data_dir / "manifest.json"
    return json.loads(f.read_text()).get("tour_hints", {}) if f.exists() else {}


def _aha(db, p: M.Project, max_lines: int) -> tuple[int, str, int | None] | None:  # type: ignore[no-untyped-def]
    run = prefer_live(db.execute(select(M.FidelityRun).where(M.FidelityRun.project_id == p.id)).scalars().all())
    if run is None:
        return None
    best: tuple[int, int, str, int | None] | None = None
    for c in db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == run.id)).scalars():
        ps = c.per_system
        base_h = {x["human_id"] for x in ps["baseline"].get("pairs", [])}
        for x in ps["lens"].get("pairs", []):
            if x["human_id"] in base_h:
                continue
            pr = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.number == c.pr_number)).scalars().first()
            size = (pr.additions + pr.deletions) if pr else 10 ** 6
            if size > max_lines:
                continue
            f = db.get(M.FindingRow, x["other_id"])
            ev = None
            for eid in (f.refs or {}).get("exemplar_finding_ids", []) if f else []:
                e = db.get(M.FindingRow, eid)
                if e is not None and e.pr_number != c.pr_number:
                    ev = e.pr_number
                    break
            key = (0 if ev else 1, size)
            if best is None or key < best[:2]:
                best = (key[0], key[1], x["other_id"], ev)
                best_n = c.pr_number
    if best is None:
        return None
    return best_n, best[2], best[3]


def build_tour(pid: str | None) -> S.Tour:
    cfg = get_config()
    tcfg = cfg.ui["tour"]
    from keeper.services import queue
    steps: dict[str, S.TourStep] = {}
    with session_scope() as db:
        try:
            p = project(db, pid)
        except NotFound:
            return S.Tour(steps=[])
        m = maintainer(db, p)
        who = name_of(m)
        aha = _aha(db, p, int(tcfg["aha_max_diff_lines"]))
        if aha:
            n, fid, ev = aha
            because = f", because of what they said on #{ev}" if ev else ""
            steps["aha_compare"] = S.TourStep(
                id="aha_compare", title="What generic review misses", route=f"/pr/{n}?view=compare",
                body_md=f"A past PR Keeper never trained on. Generic review missed this; {who} caught it, and so did "
                        f"{who}'s lens{because}.", target=S.TourTarget(kind="compare_pair", id=fid),
                reason="held-out PR where the lens matched the maintainer and the baseline didn't")
        hint = _manifest_hints().get("fix_demo")
        fixes = db.execute(select(M.FixRun).where(M.FixRun.project_id == p.id, M.FixRun.status == "passed")).scalars().all()
        fx = prefer_live([f for f in fixes if f.pr_number == hint] or fixes)
        if fx is not None:
            two = (fx.iterations or 1) > 1
            steps["fix_demo"] = S.TourStep(
                id="fix_demo", title="Fixed and tested", route=f"/pr/{fx.pr_number}/fix/{fx.id}",
                body_md=f"Keeper wrote the fix {who} would ask for and ran the tests."
                        + (" The first try failed; the second passed." if two else " The tests passed."),
                target=S.TourTarget(kind="fix_timeline"), reason="a passing fix run")
        pid_ = p.id
    q = queue.get_queue(pid_)
    s = q.summary
    if s.total:
        steps["queue_summary"] = S.TourStep(
            id="queue_summary", title="Today's queue", route="/queue",
            body_md=f"Today's queue: {s.total} open PRs. Only {s.need_count} need {who}: about "
                    f"{s.attention_minutes_total} min. The rest are handled or handed off.",
            target=S.TourTarget(kind="lane_summary"), reason="queue summary")
    unk = next((r for r in q.items if r.lane == "unknown"), None)
    if unk is not None:
        sig = next((x.label for x in unk.signals if not x.covered), None) or (unk.reasons[0].label if unk.reasons else
                                                                             "a risk signal")
        rev = f"{unk.handoff.display_name or unk.handoff.login}" if unk.handoff else "another reviewer"
        steps["unknown_row"] = S.TourStep(
            id="unknown_row", title="Knowing what it doesn't know", route="/queue",
            body_md=f"This one is outside what Keeper knows about {who}: {sig.lower()}. So it suggests {rev} instead "
                    "of guessing.", target=S.TourTarget(kind="queue_row", id=str(unk.number)),
            reason="first PR in the unknown lane")
    with session_scope() as db:
        p = project(db, pid_)
        lens = db.execute(select(M.Lens).where(M.Lens.project_id == p.id, M.Lens.person_id == m.id)).scalars().first()
        if lens is not None:
            lv = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id, M.LensVersion.status == "ready")
                            .order_by(M.LensVersion.version.desc())).scalars().first()
            if lv and db.execute(select(M.EdgeMapCell.id).where(M.EdgeMapCell.lens_version_id == lv.id,
                                                                M.EdgeMapCell.kind == "top")).first():
                steps["edge_map"] = S.TourStep(
                    id="edge_map", title="Where attention matters", route="/lens?tab=map",
                    body_md=f"This is where {who}'s eye matters most, and where generic review is enough.",
                    target=S.TourTarget(kind="edge_top"), reason="edge map has top cells")
        run = prefer_live(db.execute(select(M.FidelityRun).where(M.FidelityRun.project_id == p.id)).scalars().all())
        if run is not None:
            k = (run.metrics or {}).get("keeper", {}).get("substantive_recall", {}).get("value")
            b = (run.metrics or {}).get("baseline", {}).get("substantive_recall", {}).get("value")
            n = int((run.holdout_spec or {}).get("prs", 0))
            verdict = "" if (run.passes or {}).get("overall") else " It didn't pass this time; the page shows why."
            steps["proof_verdict"] = S.TourStep(
                id="proof_verdict", title="The proof", route="/proof",
                body_md=f"Tested on {n} PRs the lens never saw: it recovered {round((k or 0) * 100)}% of what {who} "
                        f"noticed, against the baseline's {round((b or 0) * 100)}%.{verdict}",
                target=S.TourTarget(kind="proof_verdict"), reason="latest fidelity run")
    steps["practice_taste"] = S.TourStep(id="practice_taste", title="Your turn", route="/practice",
                                         body_md=f"Your turn: can you spot what {who} would?",
                                         target=S.TourTarget(kind="practice_taste"), reason="always available")
    return S.Tour(steps=[steps[k] for k in tcfg["steps"] if k in steps])

"""L10: the maintainer's growth residual G = H − L and the period measures (methodology 12 Part B)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.core.timeutil import add_months
from keeper.db import models as M
from keeper.db import repo as R
from keeper.growth import health as H
from keeper.ids import stable_id
from keeper.outcomes.link import addressed


def periods(start: datetime, end: datetime, months: int) -> list[tuple[datetime, datetime]]:
    out = []
    t = end
    while t > start:
        s = add_months(t, -months)
        out.append((max(s, start), t))
        t = s
    return list(reversed(out))


def compute(db: Session, project: M.Project, lens: M.Lens, person: M.Person, ruler_id: str,
            fidelity_run: M.FidelityRun | None, *, origin: str = "live") -> dict[str, Any]:
    cfg = get_config()
    g = cfg.growth["growth"]
    pulls = {p.number: p for p in db.execute(select(M.Pull).where(M.Pull.project_id == project.id)).scalars()}
    samples = db.execute(select(M.ResidualSample).where(M.ResidualSample.person_id == person.id,
                                                        M.ResidualSample.ruler_id == ruler_id)).scalars().all()
    own = {f.id: f for f in R.findings(db, project.id, source="human", person_id=person.id, context="history")}
    links = {fid for (fid,) in db.execute(select(M.OutcomeLink.finding_id))}
    versions = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id).order_by(M.LensVersion.version)
                          ).scalars().all()
    bs_keys: set[str] = set()
    for v in versions:
        for it in db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == v.id,
                                                         M.LensItemRow.type == "blind_spot")).scalars():
            bs_keys.add(it.category)
    if not samples:
        return {"health_state": "insufficient_data", "snapshots": []}
    start = min(pulls[s.pr_number].created_at for s in samples if s.pr_number in pulls)
    end = project.demo_now or max(p.created_at for p in pulls.values())
    window = int(cfg.matching["line_window"])
    by_pr: dict[int, list[M.ResidualSample]] = defaultdict(list)
    for s in samples:
        by_pr[s.pr_number].append(s)
    # G per held-out PR: P's findings that lens v_k (the fidelity run's version) did not predict
    g_by_pr: dict[int, dict[str, Any]] = {}
    if fidelity_run is not None:
        for c in db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == fidelity_run.id)).scalars():
            ps = c.per_system
            lens_hit = set(ps["lens"]["matched_h"])
            base_hit = set(ps["baseline"]["matched_h"])
            gids = [h for h in ps["h"] if h not in lens_hit]
            g_by_pr[c.pr_number] = {"g": gids, "g_novel": [h for h in gids if h not in base_hit]}
    snaps = []
    db.execute(delete(M.GrowthSnapshot).where(M.GrowthSnapshot.lens_id == lens.id, M.GrowthSnapshot.origin == origin))
    for a, b in periods(start, end, int(g["period_months"])):
        prs = [n for n, ss in by_pr.items() if a <= pulls[n].created_at < b]
        if not prs:
            continue
        rplus = [s for n in prs for s in by_pr[n] if s.klass == "r_plus" and s.finding_id in own and
                 own[s.finding_id].substantive]
        shared = [s for n in prs for s in by_pr[n] if s.klass == "shared"]
        rminus = [s for n in prs for s in by_pr[n] if s.klass == "r_minus"]
        hits = 0
        merged_rplus = 0
        for s in rplus:
            pr = pulls[s.pr_number]
            if pr.merged_at is None:
                continue
            merged_rplus += 1
            f = own[s.finding_id]
            if addressed(db, project, pr, f, window) or f.id in links:
                hits += 1
        costly = 0
        for s in rminus:
            f = db.get(M.FindingRow, s.finding_id)
            if f is not None and f.category in bs_keys and f.id in links:
                costly += 1
        gp = [g_by_pr[n] for n in prs if n in g_by_pr]
        m = {"prs": len(prs), "r_plus_rate": round(len(rplus) / len(prs), 3),
             "r_plus_hit": round(hits / merged_rplus, 3) if merged_rplus else None,
             "costly_r_minus_rate": round(costly / len(prs), 3),
             "shared_share": round(len(shared) / max(1, len(shared) + len(rplus)), 3),
             "g_rate": round(sum(len(x["g"]) for x in gp) / len(gp), 3) if gp else None,
             "g_novel_rate": round(sum(len(x["g_novel"]) for x in gp) / len(gp), 3) if gp else None,
             "assisted_share": 0.0, "unassisted_recall": None}
        snaps.append({"period_start": a, "period_end": b, "measures": m})
    st, trend = H.state([s["measures"] for s in snaps], cfg.growth)
    g_examples = [gid for x in g_by_pr.values() for gid in x["g_novel"]][:8]
    if snaps:
        snaps[-1]["measures"]["g_examples"] = g_examples
    explanations = cfg.growth.get("explanations", {})
    for i, s in enumerate(snaps):
        state_i = H.state([x["measures"] for x in snaps[: i + 1]], cfg.growth)[0] if i else "insufficient_data"
        db.add(M.GrowthSnapshot(id=stable_id("gro", lens.id, s["period_start"].isoformat(), origin), lens_id=lens.id,
                                period_start=s["period_start"], period_end=s["period_end"], measures=s["measures"],
                                health_state=state_i, explanation=explanations.get(state_i), origin=origin))
    db.flush()
    tr = None
    if len(snaps) >= 2:
        c, p = snaps[-1]["measures"], snaps[-2]["measures"]
        tr = {"r_plus_rate": c["r_plus_rate"], "r_plus_rate_prev": p["r_plus_rate"],
              "r_plus_hit": c["r_plus_hit"] or 0, "r_plus_hit_prev": p["r_plus_hit"] or 0}
    return {"health_state": st, "trend_flags": trend, "snapshots": snaps, "g_examples": g_examples, "trend": tr}

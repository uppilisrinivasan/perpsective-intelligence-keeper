"""L9: the Perspective Fidelity Test (methodology 11). Held-out PRs after the lens cutoff; no leakage; three
systems (baseline, lens, Keeper) matched against what the person actually raised; bootstrap CIs; pass criteria."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.analysis.context import build_context, hunk_excerpt
from keeper.baseline.review import baseline_review
from keeper.config import get_config
from keeper.core.errors import RulerMismatch
from keeper.core.types import Finding, Matching
from keeper.db import models as M
from keeper.db import repo as R
from keeper.fidelity import bootstrap as BS
from keeper.fidelity import metrics as MT
from keeper.ids import stable_id
from keeper.lens.apply import apply_lens, load_items
from keeper.outcomes.link import link
from keeper.residual.match import match
from keeper.route.lanes import pr_lane, route_findings


def holdout_prs(db: Session, project: M.Project, person: M.Person, lv: M.LensVersion) -> list[M.Pull]:
    cfg = get_config().fidelity["holdout"]
    pulls = db.execute(select(M.Pull).where(M.Pull.project_id == project.id, M.Pull.created_at >= lv.cutoff_at,
                                            M.Pull.state == "closed").order_by(M.Pull.number)).scalars().all()
    end = project.demo_now
    out = []
    for p in pulls:
        if end and p.closed_at and p.closed_at > end:
            continue
        hs = [f for f in R.findings(db, project.id, pr_number=p.number, source="human", person_id=person.id,
                                    context="history") if f.substantive]
        if len(hs) >= int(cfg["min_findings"]) and not p.draft:
            out.append(p)
    return out


def _system(h: list[Finding], x: list[Finding], m: Matching, noise_ok: set[str]) -> dict[str, Any]:
    matched_h = {p.b_id: p.weight for p in m.pairs}
    used_x = {p.a_id for p in m.pairs}
    noise = sum(1 for f in x if f.substantive and f.id not in used_x and f.id not in noise_ok)
    return {"n": sum(1 for f in x if f.substantive), "matched_w": sum(matched_h.values()),
            "matched_h": sorted(matched_h), "weight_of": matched_h, "noise": noise,
            "cats": Counter(f.category for f in x if f.substantive), "ids": [f.id for f in x],
            "pairs": [{"human_id": p.b_id, "other_id": p.a_id, "decision": p.decision} for p in m.pairs]}


async def run_fidelity(db: Session, project: M.Project, person: M.Person, lv: M.LensVersion, ruler: M.Ruler, *,
                       gateway: Any, job: Any = None, origin: str = "live", run_id: str | None = None) -> M.FidelityRun:
    cfg = get_config()
    fcfg = cfg.fidelity
    if lv.ruler_id != ruler.id:
        raise RulerMismatch("This lens version was built under a different generic-review ruler.",
                            {"lens_ruler": lv.ruler_id, "run_ruler": ruler.id})
    prs = holdout_prs(db, project, person, lv)
    rid = run_id or stable_id("fid", project.id, lv.id, ruler.id, origin)
    db.execute(delete(M.FidelityCase).where(M.FidelityCase.run_id == rid))
    db.execute(delete(M.FidelityRun).where(M.FidelityRun.id == rid))
    run = M.FidelityRun(id=rid, project_id=project.id, person_id=person.id, lens_version_id=lv.id, ruler_id=ruler.id,
                        holdout_spec={"from": lv.cutoff_at.isoformat(), "to": project.demo_now.isoformat()
                                      if project.demo_now else None, "prs": len(prs)},
                        status="running", job_id=job.id if job else None, origin=origin)
    db.add(run)
    db.flush()
    items = {i.id: i for i in load_items(db, lv.id)}
    cases: list[dict[str, Any]] = []
    lanes: dict[int, str] = {}
    window = int(cfg.matching["line_window"])
    all_pairs: list[dict[str, Any]] = []
    for k, pr in enumerate(prs):
        h = [f for f in R.findings(db, project.id, pr_number=pr.number, source="human", person_id=person.id,
                                   context="history") if f.substantive]
        head = h[0].head_sha or pr.head_sha
        ctx, block = build_context(db, project, pr, head_sha=head)
        base, _ = await baseline_review(db, project, ctx, block, ruler, gateway=gateway,
                                        job_id=job.id if job else None, context="history", origin=origin)
        # strict leakage control: exemplars before both the PR and the cutoff (allow_rolling_exemplars: false)
        before = lv.cutoff_at if not fcfg["leakage"]["allow_rolling_exemplars"] else pr.created_at
        lens, meta = await apply_lens(db, project, pr, ctx, block, lv, person, ruler.id, gateway=gateway,
                                      job_id=job.id if job else None, context="fidelity", exemplars_before=before,
                                      origin=origin)
        db.execute(delete(M.FindingRow).where(M.FindingRow.project_id == project.id,
                                              M.FindingRow.pr_number == pr.number, M.FindingRow.source == "lens",
                                              M.FindingRow.lens_version_id == lv.id, M.FindingRow.context == "fidelity"))
        for f in lens:
            db.add(R.to_row(f, origin=origin, context="fidelity", lens_version_id=lv.id, ruler_id=ruler.id,
                            title=f.refs.get("title")))
        hk = lambda f, ctx=ctx: hunk_excerpt(ctx, f.anchor.path, f.anchor.start_line, 8)  # noqa: E731
        lb, _ = await match(lens, base, cfg.matching, gateway=gateway, job_id=job.id if job else None,
                            feature="proof", hunk=hk)
        from keeper.analysis.pipeline import blind_spot_matches
        bsm = blind_spot_matches(base, lb, list(items.values()))
        routed = route_findings(lens, base, lb, bsm, cfg.taxonomy)
        lanes[pr.number] = pr_lane(routed, [])
        keeper_ids = {r.finding_id for r in routed if r.lane in ("shared", "edge", "blind_spot")}
        keeper = [f for f in lens + base if f.id in keeper_ids]
        ml, _ = await match(lens, h, cfg.matching, gateway=gateway, job_id=job.id if job else None, feature="proof", hunk=hk)
        mb, _ = await match(base, h, cfg.matching, gateway=gateway, job_id=job.id if job else None, feature="proof", hunk=hk)
        mk, _ = await match(keeper, h, cfg.matching, gateway=gateway, job_id=job.id if job else None, feature="proof", hunk=hk)
        db.flush()
        link(db, project, lens + base, window)
        linked = {fid for (fid,) in db.execute(select(M.OutcomeLink.finding_id).where(
            M.OutcomeLink.finding_id.in_([f.id for f in lens + base])))}
        case = {"pr": pr.number, "title": pr.title, "h": [{"id": f.id, "category": f.category} for f in h],
                "h_cats": Counter(f.category for f in h),
                "r_plus": [hid for hid in (x.b_id for x in [])] or [f.id for f in h if f.id not in
                                                                    {p.b_id for p in mb.pairs}],
                "systems": {"baseline": _system(h, base, mb, linked), "lens": _system(h, lens, ml, linked),
                            "keeper": _system(h, keeper, mk, linked)},
                "lens_baseline_pairs": [{"baseline_id": p.b_id, "lens_id": p.a_id, "decision": p.decision}
                                        for p in lb.pairs], "recall_mode": meta.get("recall_mode")}
        cases.append(case)
        for name, m in (("lens", ml), ("baseline", mb)):
            for p in m.judged:
                all_pairs.append({"system": name, "pr": pr.number, "a": p.a_id, "b": p.b_id, "decision": p.decision,
                                  "weight": p.weight})
        if job is not None:
            await job.event("fidelity.case", {"pr_number": pr.number, "done": k + 1, "total": len(prs)})
            await job.progress(k + 1, len(prs), stage="fidelity")
    metrics, ci_all = compute(cases, fcfg)
    diff = BS.paired_difference(cases, "keeper", "baseline", int(fcfg["bootstrap"]["n"]), int(fcfg["bootstrap"]["seed"]),
                                float(fcfg["bootstrap"]["ci"]))
    run.metrics = metrics
    run.ci = {"paired_difference": diff, **ci_all}
    run.sensitivity = sensitivity(cases, all_pairs)
    run.passes = criteria(metrics, diff, fcfg, routing=None)
    run.status = "succeeded"
    run.measurement = {"lanes": lanes, "judged_pairs": len(all_pairs)}
    run.models = sorted({m for m in [r for r in []]})
    run.cost_usd = round(float(job.cost_usd), 4) if job else 0.0
    for c in cases:
        per = {name: {k2: v for k2, v in s.items() if k2 in ("n", "matched_w", "matched_h", "noise", "ids", "pairs")}
               for name, s in c["systems"].items()}
        per["h"] = [x["id"] for x in c["h"]]
        per["lens_baseline_pairs"] = c["lens_baseline_pairs"]
        per["r_plus"] = c["r_plus"]
        db.add(M.FidelityCase(run_id=rid, pr_number=c["pr"], per_system=per, notes=c.get("recall_mode")))
    db.flush()
    return run


def compute(cases: list[dict[str, Any]], fcfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    b = fcfg["bootstrap"]
    n, seed, level = int(b["n"]), int(b["seed"]), float(b["ci"])
    top_k = int(fcfg["caricature"]["top_k"])
    out: dict[str, Any] = {}
    cis: dict[str, Any] = {}
    h_cats = MT.rates(cases, "h")
    for s in MT.SYSTEMS:
        rec = MT.recall(cases, s)
        lo, hi = BS.ci(cases, lambda cs, s=s: MT.recall(cs, s), n, seed, level)
        noise = MT.noise_per_pr(cases, s)
        nlo, nhi = BS.ci(cases, lambda cs, s=s: MT.noise_per_pr(cs, s), n, seed + 3, level)
        prec = MT.precision(cases, s)
        car, ratios = MT.caricature(cases, s, top_k)
        js = MT.jsd(MT.rates(cases, s), h_cats)
        entry = {"substantive_recall": {"value": rec, "low": lo, "high": hi, "n": len(cases)},
                 "noise_per_pr": {"value": noise, "low": nlo, "high": nhi, "n": len(cases)},
                 "precision": {"value": prec}, "caricature_ratio": {"value": car, "ratios": ratios},
                 "jsd": {"value": js}, "per_category": MT.per_category(cases, s)}
        if s != "baseline":
            rr = MT.residual_recall(cases, s)
            rlo, rhi = BS.ci(cases, lambda cs, s=s: MT.residual_recall(cs, s), n, seed + 5, level)
            entry["residual_recall"] = {"value": rr, "low": rlo, "high": rhi}
        else:
            entry["residual_recall"] = {"value": 0.0}
        out[s] = entry
    return out, cis


def criteria(metrics: dict[str, Any], diff: dict[str, Any], fcfg: dict[str, Any], routing: dict[str, Any] | None
             ) -> dict[str, Any]:
    k, b, lns = metrics["keeper"], metrics["baseline"], metrics["lens"]
    max_noise = float(fcfg["pass"]["max_noise_ratio"])
    c = {
        "recall_beats_baseline": bool(k["substantive_recall"]["value"] is not None and b["substantive_recall"]["value"] is not None
                                      and k["substantive_recall"]["value"] > b["substantive_recall"]["value"]
                                      and (diff.get("low") or 0) > 0),
        "noise_not_worse": bool(k["noise_per_pr"]["value"] is not None and b["noise_per_pr"]["value"] is not None and
                                k["noise_per_pr"]["value"] <= b["noise_per_pr"]["value"] * max_noise + 1e-9),
        "no_caricature": bool(lns["caricature_ratio"]["value"] is not None and
                              lns["caricature_ratio"]["value"] <= float(fcfg["caricature"]["max_ratio"]) and
                              (lns["jsd"]["value"] or 0) <= (b["jsd"]["value"] or 0) + 1e-9),
    }
    if routing is not None and routing.get("unknown_recall") is not None:
        c["unknown_lane_recall"] = routing["unknown_recall"] >= float(fcfg["pass"]["require_unknown_recall_demo"])
    c["overall"] = all(v for v in c.values())
    return c


def sensitivity(cases: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Partial matches counted as 0 and as 1 (re-weighting the judged pairs; no new model calls)."""
    out = {}
    for label, w in (("partial_as_0", 0.0), ("partial_as_1", 1.0)):
        for system in ("lens", "baseline"):
            num = sum((1.0 if p["decision"] == "match" else w if p["decision"] == "partial" else 0.0)
                      for p in pairs if p["system"] == system and p["weight"] > 0)
            den = sum(len(c["h"]) for c in cases)
            out[f"{system}_{label}"] = round(num / den, 3) if den else None
    return out

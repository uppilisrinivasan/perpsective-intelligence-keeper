"""Measure Keeper's results in the database against the ground truth. Every metric says what it was computed on;
metrics that need data the run doesn't have are reported as not measured, never guessed."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.db import models as M
from keeper.eval import truth as T
from keeper.services.common import current_version, lens_of, maintainer, prefer_live


def _near(f: M.FindingRow, locs: list[dict[str, Any]], window: int) -> bool:
    if not locs:
        return False
    for loc in locs:
        if f.path == loc.get("path") and (f.start_line is None or loc.get("line") is None or
                                          abs(int(f.start_line) - int(loc["line"])) <= window):
            return True
    return False


def extraction(db: Session, p: M.Project) -> dict[str, Any]:
    """Comments that carry a planted concern should become substantive findings; social ones and questions not."""
    by_comment: dict[int, bool] = {}
    for f in db.execute(select(M.FindingRow).where(M.FindingRow.project_id == p.id, M.FindingRow.source == "human",
                                                   M.FindingRow.context == "history")).scalars():
        for cid in (f.refs or {}).get("comment_ids", []):
            by_comment[int(cid)] = by_comment.get(int(cid), False) or bool(f.substantive)
    tp = fp = fn = 0
    for c in T.comments():
        if c.get("comment_kind") not in ("review_comment", "review", "issue_comment"):
            continue
        want = bool(c.get("planted"))
        got = by_comment.get(int(c["id"]), False)
        tp += want and got
        fp += got and not want
        fn += want and not got
    return {"precision": round(tp / (tp + fp), 3) if tp + fp else None, "recall": round(tp / (tp + fn), 3) if tp + fn
            else None, "n": tp + fp + fn}


def _f1(rows: list[tuple[str, str]], labels: list[str]) -> float | None:
    if not rows:
        return None
    fs = []
    for lab in labels:
        tp = sum(1 for e, g in rows if e == lab and g == lab)
        fp = sum(1 for e, g in rows if e != lab and g == lab)
        fn = sum(1 for e, g in rows if e == lab and g != lab)
        if tp + fp + fn == 0:
            continue
        fs.append(2 * tp / (2 * tp + fp + fn))
    return round(sum(fs) / len(fs), 3) if fs else None


def routing(db: Session, p: M.Project) -> dict[str, Any]:
    from keeper.services import views as V
    expected = {r["pr_number"]: r for r in T.pr_lanes()}
    live, hold = [], []
    for pr in db.execute(select(M.Pull).where(M.Pull.project_id == p.id)).scalars():
        e = expected.get(pr.number)
        if e is None:
            continue
        a = V.current_analysis(db, p.id, pr, ("queue", "history"))
        if a is None:
            continue
        (live if pr.split == "live" else hold).append((e["expected_lane"], V.effective_lane(db, p.id, a)))
    labels = ["edge", "blind_spot", "unknown", "shared"]
    unk = [g for e, g in live + hold if e == "unknown"]
    return {"macro_f1": _f1(live, labels), "n_live": len(live), "holdout_macro_f1": _f1(hold, labels),
            "n_holdout": len(hold), "unknown_recall": round(sum(1 for g in unk if g == "unknown") / len(unk), 3)
            if unk else None, "confusion": dict(Counter(f"{e}→{g}" for e, g in live + hold))}


def baseline(db: Session, p: M.Project) -> dict[str, Any]:
    """Generic review should catch shared slots and blind-spot slots where they are present."""
    window = int(get_config().matching["line_window"])
    sl = T.slots()
    base: dict[int, list[M.FindingRow]] = defaultdict(list)
    for f in db.execute(select(M.FindingRow).where(M.FindingRow.project_id == p.id,
                                                   M.FindingRow.source == "baseline")).scalars():
        base[f.pr_number].append(f)
    hit: dict[str, list[bool]] = defaultdict(list)
    for r in T.pr_slots():
        typ = sl.get(r["slot"], {}).get("type")
        if not r.get("present") or typ not in ("shared", "blind_spot") or r["pr_number"] not in base:
            continue
        hit[typ].append(any(_near(f, r.get("locations", []), window) for f in base[r["pr_number"]]))
    return {f"{k}_slot_recall": round(sum(v) / len(v), 3) if v else None for k, v in
            (("shared", hit["shared"]), ("blind_spot", hit["blind_spot"]))} | {
        "n": {k: len(v) for k, v in hit.items()}}


def lens(db: Session, p: M.Project) -> dict[str, Any]:
    """Edge slots the lens represents: a validated edge item whose members are mostly findings at that slot."""
    m = maintainer(db, p)
    lv = current_version(db, lens_of(db, p, m.id))
    if lv is None:
        return {"measured": False}
    window = int(get_config().matching["line_window"])
    sl = T.slots()
    locs: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for r in T.pr_slots():
        if r.get("present"):
            locs[(r["pr_number"], r["slot"])] = r.get("locations", [])
    covered: set[str] = set()
    bs_items = 0
    share = float(T.thresholds().get("lens", {}).get("member_share", 0.6))
    for it in db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lv.id)).scalars():
        if it.status != "validated":
            continue
        if it.type == "blind_spot":
            bs_items += 1
            continue
        if it.type != "edge":
            continue
        mem = [db.get(M.FindingRow, e.finding_id) for e in db.execute(select(M.LensItemEvidence).where(
            M.LensItemEvidence.lens_item_id == it.id, M.LensItemEvidence.role == "member")).scalars() if e.finding_id]
        mem = [f for f in mem if f is not None]
        if not mem:
            continue
        per_slot: Counter[str] = Counter()
        for f in mem:
            for (n, s), ls in locs.items():
                if n == f.pr_number and sl.get(s, {}).get("type") == "edge" and _near(f, ls, window):
                    per_slot[s] += 1
                    break
        if per_slot:
            s, c = per_slot.most_common(1)[0]
            if c / len(mem) >= share:
                covered.add(s)
    return {"measured": True, "version": lv.version, "edge_slots_covered": sorted(covered),
            "edge_slot_coverage": len(covered), "blind_spot_items": bs_items}


def edge_map(db: Session, p: M.Project) -> dict[str, Any]:
    m = maintainer(db, p)
    lv = current_version(db, lens_of(db, p, m.id))
    if lv is None:
        return {"measured": False}
    top = db.execute(select(M.EdgeMapCell).where(M.EdgeMapCell.lens_version_id == lv.id, M.EdgeMapCell.kind == "top")
                     .order_by(M.EdgeMapCell.value.desc())).scalars().all()[:4]
    planted = {(a, s["category"]) for s in T.slots().values() if s["type"] == "edge" for a in s.get("areas", [])}
    hits = sum(1 for c in top if (c.area.split("/")[-1], c.category) in planted)
    return {"measured": True, "planted_in_top4": hits, "top4": [f"{c.area}·{c.category}" for c in top]}


def fix(db: Session, p: M.Project) -> dict[str, Any]:
    runs = db.execute(select(M.FixRun).where(M.FixRun.project_id == p.id)).scalars().all()
    by_pr: dict[int, list[M.FixRun]] = defaultdict(list)
    for r in runs:
        by_pr[r.pr_number].append(r)
    latest = [prefer_live(v) for v in by_pr.values()]
    ok = sum(1 for r in latest if r.status == "passed")
    return {"success": round(ok / len(latest), 3) if latest else None, "n": len(latest)}


def run(db: Session, p: M.Project) -> dict[str, Any]:
    out = {"extraction": extraction(db, p), "routing": routing(db, p), "baseline": baseline(db, p),
           "lens": lens(db, p), "edge_map": edge_map(db, p), "fix": fix(db, p),
           "matching": {"kappa": None, "note": "needs human-labelled match pairs; not measured"}}
    th = get_config().eval
    checks = []

    def chk(area: str, key: str, value: Any, need: Any, kind: str = "min") -> None:
        if value is None:
            checks.append({"metric": f"{area}.{key}", "value": None, "target": need, "pass": None})
            return
        ok = value >= need if kind == "min" else value == need
        checks.append({"metric": f"{area}.{key}", "value": value, "target": need, "pass": bool(ok)})
    chk("extraction", "precision", out["extraction"]["precision"], th["extraction"]["precision_min"])
    chk("extraction", "recall", out["extraction"]["recall"], th["extraction"]["recall_min"])
    chk("routing", "macro_f1", out["routing"]["macro_f1"], th["routing"]["macro_f1_min"])
    chk("routing", "holdout_macro_f1", out["routing"]["holdout_macro_f1"], th["routing"]["holdout_macro_f1_min"])
    chk("routing", "unknown_recall", out["routing"]["unknown_recall"], th["routing"]["unknown_recall"])
    chk("baseline", "shared_slot_recall", out["baseline"]["shared_slot_recall"], th["baseline"]["shared_slot_recall_min"])
    chk("baseline", "blind_spot_slot_recall", out["baseline"]["blind_spot_slot_recall"],
        th["baseline"]["blind_spot_slot_recall_min"])
    chk("lens", "edge_slot_coverage", out["lens"].get("edge_slot_coverage"), th["lens"]["edge_slot_coverage_min"])
    chk("lens", "blind_spot_items", out["lens"].get("blind_spot_items"), th["lens"]["blind_spot_items"])
    chk("edge_map", "planted_in_top4", out["edge_map"].get("planted_in_top4"), th["edge_map"]["planted_in_top4_min"])
    chk("fix", "success", out["fix"]["success"], th["fix"]["success_min"])
    chk("matching", "kappa", None, th["matching"]["kappa_min"])
    out["checks"] = checks
    return out

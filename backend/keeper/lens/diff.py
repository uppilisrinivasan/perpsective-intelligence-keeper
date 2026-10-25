"""The lens diff between two versions (methodology 13 §2). Pure: two item lists in, a changelog out."""

from __future__ import annotations

from typing import Any

from keeper.core.textsim import similarity


def _rate(it: dict[str, Any]) -> float:
    return float((it.get("stats") or {}).get("outcome", {}).get("posterior_mean") or 0)


def diff(a: list[dict[str, Any]], b: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Items as dicts with id, stable_key, type, title, statement, category, status, stats."""
    d = cfg["diff"]
    out: list[dict[str, Any]] = []
    a_by = {i["stable_key"]: i for i in a}
    matched_a: set[str] = set()
    for ib in b:
        ia = a_by.get(ib["stable_key"])
        if ia is None:
            cands = [x for x in a if x["category"] == ib["category"] and x["stable_key"] not in matched_a and
                     x["type"] == ib["type"]]
            best = max(cands, key=lambda x: similarity(x["statement"], ib["statement"]), default=None)
            if best is not None and similarity(best["statement"], ib["statement"]) >= float(d["new_id_similarity"]):
                ia = best
        if ia is None:
            out.append({"change": "added", "item": ib})
            continue
        matched_a.add(ia["stable_key"])
        if similarity(ia["statement"], ib["statement"]) < float(d["reworded_below"]):
            out.append({"change": "reworded", "item": ib, "from": ia["statement"], "to": ib["statement"]})
        sa, sb = (ia.get("stats") or {}).get("support", 0), (ib.get("stats") or {}).get("support", 0)
        ra, rb = _rate(ia), _rate(ib)
        rel = max(abs(sb - sa) / max(1, sa), abs(rb - ra) / max(ra, 1e-9) if ra else 0)
        if rel >= float(d["strength_change"]):
            out.append({"change": "strengthened" if (sb > sa or rb > ra) else "weakened", "item": ib,
                        "from": {"support": sa, "hit_rate": ra}, "to": {"support": sb, "hit_rate": rb}})
        if ia["status"] != ib["status"]:
            out.append({"change": "status_changed", "item": ib, "from": ia["status"], "to": ib["status"]})
        if ib["status"] == "retired" and ia["status"] != "retired":
            out.append({"change": "retired", "item": ib})
    for ia in a:
        if ia["stable_key"] not in matched_a:
            out.append({"change": "blind_spot_closed" if ia["type"] == "blind_spot" else "retired", "item": ia})
    return out

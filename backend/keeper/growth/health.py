"""Health states of a person's growth (methodology 12 §B3). Pure, table-driven; the first matching rule wins."""

from __future__ import annotations

from typing import Any


def _trend(cur: float | None, prev: float | None, deadband: float) -> int:
    if cur is None or prev is None:
        return 0
    if prev == 0:
        return 1 if cur > deadband else 0
    rel = (cur - prev) / abs(prev)
    return 1 if rel > deadband else (-1 if rel < -deadband else 0)


def state(periods: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    g = cfg["growth"]
    if len(periods) < 2:
        return "insufficient_data", {}
    prev, cur = periods[-2], periods[-1]
    if prev.get("prs", 0) < int(g["min_prs_per_period"]) or cur.get("prs", 0) < int(g["min_prs_per_period"]):
        return "insufficient_data", {}
    db = float(g["deadband"])
    t = {k: _trend(cur.get(k), prev.get(k), db) for k in ("r_plus_rate", "r_plus_hit", "costly_r_minus_rate",
                                                         "shared_share", "assisted_share", "unassisted_recall")}
    floor = float(g["g_floor"])
    if cur.get("g_rate") is not None and prev.get("g_rate") is not None and cur["g_rate"] <= floor and prev["g_rate"] <= floor:
        return "replaced", t
    if cur.get("assisted_share") is not None and cur.get("unassisted_recall") is not None and \
            t["assisted_share"] > 0 and t["unassisted_recall"] < 0:
        return "deskilling", t
    if t["r_plus_rate"] > 0 and t["r_plus_hit"] < 0:
        return "self_caricature", t
    if t["r_plus_rate"] < 0 and t["costly_r_minus_rate"] < 0 and t["shared_share"] > 0:
        return "absorbed", t
    return "healthy", t

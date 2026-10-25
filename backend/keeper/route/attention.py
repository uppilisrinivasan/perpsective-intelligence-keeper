"""Attention estimates (methodology 07 §4.2). Configuration, not claims: labelled "≈" in the UI."""

from __future__ import annotations

import math
from typing import Any

from keeper.core.types import RoutedFinding


def attention_minutes(pr_lane: str, routed: list[RoutedFinding], changed_lines: int, cfg: dict[str, Any], *,
                      edge_map_bonus: float = 0.0, fixed_shared: int = 0) -> int:
    a = cfg["attention"]
    total = float(a["lane_base"][pr_lane])
    per = a["per_finding"]
    for r in routed:
        if r.lane in per:
            total += float(per[r.lane])
    total += float(a["per_100_changed_lines"]) * changed_lines / 100 * float(a["lane_size_factor"][pr_lane])
    total += edge_map_bonus
    total -= float(a["fixed_and_tested_discount"]) * fixed_shared
    lo, hi = a["clamp"]
    return int(math.ceil(min(max(total, lo), hi)))


def naive_minutes(changed_lines: list[int], cfg: dict[str, Any]) -> int:
    a = cfg["attention"]
    return int(math.ceil(sum(float(a["naive_base"]) + float(a["naive_per_100"]) * n / 100 for n in changed_lines)))

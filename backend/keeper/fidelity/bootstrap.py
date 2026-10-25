"""Percentile bootstrap over PRs (methodology 11 §3). Pure and seeded."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


def ci(cases: list[dict[str, Any]], stat: Callable[[list[dict[str, Any]]], float | None], n: int, seed: int,
       level: float) -> tuple[float | None, float | None]:
    if not cases:
        return None, None
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        sample = [cases[i] for i in rng.integers(0, len(cases), len(cases))]
        v = stat(sample)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    lo, hi = np.percentile(vals, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def paired_difference(cases: list[dict[str, Any]], a: str, b: str, n: int, seed: int, level: float
                      ) -> dict[str, float | None]:
    """Bootstrap the difference in substantive recall (a − b) over PRs; p = share of resamples ≤ 0."""
    from keeper.fidelity.metrics import recall

    if not cases:
        return {"value": None, "low": None, "high": None, "p": None}
    rng = np.random.default_rng(seed + 1)
    diffs = []
    for _ in range(n):
        s = [cases[i] for i in rng.integers(0, len(cases), len(cases))]
        ra, rb = recall(s, a), recall(s, b)
        if ra is not None and rb is not None:
            diffs.append(ra - rb)
    point = (recall(cases, a) or 0) - (recall(cases, b) or 0)
    lo, hi = np.percentile(diffs, [(1 - level) / 2 * 100, (1 + level) / 2 * 100]) if diffs else (None, None)
    p = float(np.mean([d <= 0 for d in diffs])) if diffs else None
    return {"value": float(point), "low": float(lo) if lo is not None else None,
            "high": float(hi) if hi is not None else None, "p": p}

"""The practice item bank and parallel forms (methodology 12 §A1–A2). Pure and seeded."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


def difficulty(findings: list[dict[str, Any]], severity_weight: dict[str, float]) -> float:
    """Σ over P's findings of (1 if the baseline also found it, else 2) × severity weight."""
    return sum((1.0 if f["baseline_found"] else 2.0) * float(severity_weight.get(f["severity"], 1.0)) for f in findings)


def bucketize(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    ds = sorted(i["difficulty"] for i in items)
    lo, hi = ds[len(ds) // 3], ds[2 * len(ds) // 3]
    for i in items:
        i["bucket"] = "easy" if i["difficulty"] <= lo else ("hard" if i["difficulty"] > hi else "medium")


def profile(items: list[dict[str, Any]]) -> dict[str, float]:
    c: Counter[str] = Counter()
    for i in items:
        c.update(i["categories"])
    n = sum(c.values()) or 1
    return {k: v / n for k, v in c.items()}


def l1(a: dict[str, float], b: dict[str, float]) -> float:
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))


def _pick(pool: list[dict[str, Any]], strata: dict[str, int], target: dict[str, float], k: int) -> list[dict[str, Any]]:
    form: list[dict[str, Any]] = []
    for bucket, n in strata.items():
        cands = [i for i in pool if i["bucket"] == bucket and i not in form]
        for _ in range(n):
            if not cands:
                break
            best = min(cands, key=lambda i: l1(profile(form + [i]), target))
            form.append(best)
            cands.remove(best)
    rest = [i for i in pool if i not in form]
    while len(form) < k and rest:
        best = min(rest, key=lambda i: l1(profile(form + [i]), target))
        form.append(best)
        rest.remove(best)
    return form


def parallel_forms(bank: list[dict[str, Any]], used: set[int], k: int, strata: dict[str, int], seed: int,
                   balance: dict[str, float], tries: int = 60) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Before and after forms, disjoint, balanced on mean difficulty and category profile."""
    pool = [i for i in bank if i["pr"] not in used]
    target = profile(bank)
    rng = np.random.default_rng(seed)
    best: tuple[float, list[dict[str, Any]], list[dict[str, Any]]] | None = None
    for t in range(tries):
        order = list(pool)
        if t:
            rng.shuffle(order)
        a = _pick(order, strata, target, k)
        b = _pick([i for i in order if i not in a], strata, target, k)
        if len(a) < k or len(b) < k:
            continue
        dd = abs(np.mean([i["difficulty"] for i in a]) - np.mean([i["difficulty"] for i in b]))
        scale = max(1.0, float(np.mean([i["difficulty"] for i in bank])))
        score = dd / scale + l1(profile(a), profile(b))
        if best is None or score < best[0]:
            best = (score, a, b)
        if dd / scale <= float(balance["max_mean_difficulty_diff"]) and l1(profile(a), profile(b)) <= \
                float(balance["max_profile_l1"]):
            break
    if best is None:
        half = len(pool) // 2
        return pool[:min(k, half)], pool[half:half + k]
    return best[1], best[2]


def balanced(a: list[dict[str, Any]], b: list[dict[str, Any]], bank: list[dict[str, Any]], balance: dict[str, float]
             ) -> bool:
    scale = max(1.0, float(np.mean([i["difficulty"] for i in bank]))) if bank else 1.0
    dd = abs(np.mean([i["difficulty"] for i in a]) - np.mean([i["difficulty"] for i in b])) / scale
    return dd <= float(balance["max_mean_difficulty_diff"]) and l1(profile(a), profile(b)) <= float(balance["max_profile_l1"])

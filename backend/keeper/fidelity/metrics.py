"""Fidelity metrics (methodology 11 §2). Pure: per-PR case records in, metrics out.

A case: {pr, h: [findings of P (substantive)], systems: {baseline|lens|keeper: {"n": findings, "matched_w": weight
of H matched, "matched_h": [h ids], "noise": unmatched-to-H-and-outcomes count, "cats": Counter}}, "r_plus": [h ids
the baseline missed]}.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

SYSTEMS = ("keeper", "lens", "baseline")


def recall(cases: list[dict[str, Any]], system: str) -> float | None:
    num = sum(c["systems"][system]["matched_w"] for c in cases)
    den = sum(len(c["h"]) for c in cases)
    return num / den if den else None


def residual_recall(cases: list[dict[str, Any]], system: str) -> float | None:
    den = sum(len(c["r_plus"]) for c in cases)
    if not den:
        return None
    num = sum(sum(1 for h in c["r_plus"] if h in c["systems"][system]["matched_h"]) for c in cases)
    return num / den


def noise_per_pr(cases: list[dict[str, Any]], system: str) -> float | None:
    return sum(c["systems"][system]["noise"] for c in cases) / len(cases) if cases else None


def precision(cases: list[dict[str, Any]], system: str) -> float | None:
    n = sum(c["systems"][system]["n"] for c in cases)
    good = sum(c["systems"][system]["n"] - c["systems"][system]["noise"] for c in cases)
    return good / n if n else None


def rates(cases: list[dict[str, Any]], key: str) -> Counter[str]:
    c: Counter[str] = Counter()
    for case in cases:
        c.update(case["h_cats"] if key == "h" else case["systems"][key]["cats"])
    return c


def caricature(cases: list[dict[str, Any]], system: str, top_k: int) -> tuple[float | None, dict[str, float]]:
    h = rates(cases, "h")
    x = rates(cases, system)
    top = [c for c, _ in h.most_common(top_k)]
    ratios = {c: (x[c] / h[c]) for c in top if h[c]}
    return (max(ratios.values()) if ratios else None), ratios


def jsd(p: Counter[str], q: Counter[str]) -> float | None:
    keys = set(p) | set(q)
    sp, sq = sum(p.values()), sum(q.values())
    if not keys or not sp or not sq:
        return None
    P = {k: p[k] / sp for k in keys}
    Q = {k: q[k] / sq for k in keys}
    M = {k: (P[k] + Q[k]) / 2 for k in keys}

    def kl(a: dict[str, float], b: dict[str, float]) -> float:
        return sum(a[k] * math.log2(a[k] / b[k]) for k in keys if a[k] > 0)
    return (kl(P, M) + kl(Q, M)) / 2


def per_category(cases: list[dict[str, Any]], system: str) -> dict[str, float]:
    num: Counter[str] = Counter()
    den: Counter[str] = Counter()
    for c in cases:
        for h in c["h"]:
            den[h["category"]] += 1
            if h["id"] in c["systems"][system]["matched_h"]:
                num[h["category"]] += c["systems"][system]["weight_of"].get(h["id"], 1.0)
    return {k: round(num[k] / den[k], 3) for k in den}


def macro_f1(pairs: list[tuple[str, str]], labels: list[str]) -> float | None:
    if not pairs:
        return None
    f1s = []
    for lab in labels:
        tp = sum(1 for e, g in pairs if e == lab and g == lab)
        fp = sum(1 for e, g in pairs if e != lab and g == lab)
        fn = sum(1 for e, g in pairs if e == lab and g != lab)
        if tp + fp + fn == 0:
            continue
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return sum(f1s) / len(f1s) if f1s else None

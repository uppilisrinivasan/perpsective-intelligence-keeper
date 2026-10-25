"""Matching and the residual R = H − C (methodology 04). Judge decisions come from `match_findings`; the
one-to-one assignment and the partition are code (scipy's linear_sum_assignment)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from keeper.core.types import Finding, Matching, MatchPair
from keeper.residual.candidates import candidates


def anchor_text(f: Finding) -> str:
    a = f.anchor
    if a.scope == "pr" or not a.path:
        return "whole PR"
    if a.scope == "file" or a.start_line is None:
        return f"{a.path} (file)"
    return f"{a.path}:{a.start_line}" + (f"-{a.end_line}" if a.end_line and a.end_line != a.start_line else "")


def assign(A: list[Finding], B: list[Finding], judged: list[MatchPair], weights: dict[str, float]) -> Matching:
    """Maximum-weight one-to-one assignment over judged pairs; unassigned partial edges are dropped."""
    m = Matching(judged=judged)
    if A and B and judged:
        ai = {f.id: i for i, f in enumerate(A)}
        bi = {f.id: j for j, f in enumerate(B)}
        w = np.zeros((len(A), len(B)))
        best: dict[tuple[int, int], MatchPair] = {}
        for p in judged:
            wt = float(weights.get(p.decision, 0.0))
            i, j = ai.get(p.a_id), bi.get(p.b_id)
            if i is None or j is None or wt <= 0:
                continue
            if wt > w[i, j]:
                w[i, j] = wt
                best[(i, j)] = p
        rows, cols = linear_sum_assignment(w, maximize=True)
        for i, j in zip(rows, cols, strict=False):
            if w[i, j] > 0:
                p = best[(i, j)]
                m.pairs.append(MatchPair(a_id=p.a_id, b_id=p.b_id, decision=p.decision, weight=float(w[i, j]),
                                         rationale=p.rationale))
    used_a = {p.a_id for p in m.pairs}
    used_b = {p.b_id for p in m.pairs}
    m.shared_a = [f.id for f in A if f.id in used_a]
    m.shared_b = [f.id for f in B if f.id in used_b]
    m.r_plus = [f.id for f in A if f.id not in used_a]
    m.r_minus = [f.id for f in B if f.id not in used_b]
    return m


async def match(A: list[Finding], B: list[Finding], cfg: dict[str, Any], *, gateway: Any,
                hunk: Callable[[Finding], str] | None = None, job_id: str | None = None,
                feature: str = "analysis", prompt: str = "match_findings") -> tuple[Matching, list[str]]:
    """Return the matching and the llm call IDs used."""
    pairs = candidates(A, B, cfg)
    judged: list[MatchPair] = []
    calls: list[str] = []
    size = int(cfg["judge_batch_size"])
    for k in range(0, len(pairs), size):
        batch = pairs[k:k + size]
        inputs = {"pairs": [{"pair_id": p["pair_id"],
                             "a": {"statement": p["a"].statement, "anchor": anchor_text(p["a"]), "category": p["a"].category},
                             "b": {"statement": p["b"].statement, "anchor": anchor_text(p["b"]), "category": p["b"].category},
                             "hunk": hunk(p["a"]) if hunk else ""} for p in batch],
                  "_sim": {"pairs": [{"pair_id": p["pair_id"], "a": p["a"].model_dump(mode="json"),
                                      "b": p["b"].model_dump(mode="json"), "pre": p["pre"], "lexical": p["lexical"],
                                      "anchor": p["anchor"], "reason": p["reason"]} for p in batch]}}
        res = await gateway.call(prompt, inputs, job_id=job_id, feature=feature)
        calls.append(res.call_id)
        by_id = {p["pair_id"]: p for p in batch}
        seen = set()
        for d in res.data.get("decisions", []):
            p = by_id.get(d.get("pair_id"))
            if p is None or d["pair_id"] in seen:
                continue
            seen.add(d["pair_id"])
            judged.append(MatchPair(a_id=p["a"].id, b_id=p["b"].id, decision=d["decision"],
                                    weight=float(cfg["weights"].get(d["decision"], 0.0)),
                                    rationale=d.get("rationale", "")))
        for pid, p in by_id.items():  # undecided pairs count as none
            if pid not in seen:
                judged.append(MatchPair(a_id=p["a"].id, b_id=p["b"].id, decision="none", weight=0.0,
                                        rationale="not decided by the judge"))
    return assign(A, B, judged, cfg["weights"]), calls

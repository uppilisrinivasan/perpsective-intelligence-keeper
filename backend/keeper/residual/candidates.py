"""Step 1 of matching: candidate pairs by code (anchor proximity, lexical similarity, category). Pure."""

from __future__ import annotations

import re
from typing import Any

from keeper.core.textsim import cosine_matrix
from keeper.core.types import Finding


def anchor_score(a: Finding, b: Finding, window: int, scores: dict[str, float]) -> float:
    if a.anchor.path is None or b.anchor.path is None or a.anchor.path != b.anchor.path:
        return 0.0
    sa, sb = a.anchor.span(), b.anchor.span()
    if sa and sb:
        if sa[0] <= sb[1] and sb[0] <= sa[1]:
            return float(scores["overlap"])
        if sa[0] - window <= sb[1] and sb[0] - window <= sa[1]:
            return float(scores["window"])
    return float(scores["same_file"])


def _mentions(statement: str, path: str | None) -> bool:
    if not path:
        return False
    base = path.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0]
    return base in statement or bool(re.search(rf"\b{re.escape(stem)}\b", statement))


def eligible(a: Finding, b: Finding) -> bool:
    if a.substantive and b.substantive:
        return True
    return a.category == "style" and b.category == "style"


def candidates(A: list[Finding], B: list[Finding], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    if not A or not B:
        return []
    window = int(cfg["line_window"])
    sims = cosine_matrix([a.statement for a in A], [b.statement for b in B])
    pre_w, anc = cfg["pre_score"], cfg["anchor_score"]
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            if not eligible(a, b):
                continue
            lex = float(sims[i, j])
            asc = anchor_score(a, b, window, anc)
            same_cat = a.category == b.category
            reason = None
            if asc >= float(anc["window"]):
                reason = "anchor"
            elif a.anchor.scope == "pr" and b.anchor.scope == "pr":
                reason = "both_pr"
            elif (a.anchor.scope == "pr" and _mentions(a.statement, b.anchor.path)) or \
                    (b.anchor.scope == "pr" and _mentions(b.statement, a.anchor.path)):
                reason = "pr_mentions_file"
            elif (a.anchor.scope == "pr" or b.anchor.scope == "pr") and same_cat:
                reason = "pr_level_same_category"  # a PR-wide concern may be the same as a located one
            elif asc > 0 and same_cat:
                reason = "same_file_category"
            elif lex >= float(cfg["min_lexical"]):
                reason = "lexical"
            if reason is None:
                continue
            pre = float(pre_w["anchor"]) * asc + float(pre_w["lexical"]) * lex + float(pre_w["category"]) * same_cat
            pairs.append({"a": a, "b": b, "pre": pre, "lexical": lex, "anchor": asc, "reason": reason})
    k = int(cfg["max_candidates_per_finding"])
    keep: set[int] = set()
    for side in ("a", "b"):
        groups: dict[str, list[int]] = {}
        for idx, p in enumerate(pairs):
            groups.setdefault(p[side].id, []).append(idx)
        for idxs in groups.values():
            keep.update(sorted(idxs, key=lambda x: -pairs[x]["pre"])[:k])
    out = [pairs[i] for i in sorted(keep)]
    for n, p in enumerate(out, start=1):
        p["pair_id"] = f"p{n}"
    return out

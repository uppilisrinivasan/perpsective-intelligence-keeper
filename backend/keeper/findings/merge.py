"""Merge duplicate findings from one source on one PR (01 §2.2): same anchor ±3 lines, same category, similar."""

from __future__ import annotations

from typing import Any

from keeper.core.textsim import cosine_matrix
from keeper.core.types import Finding


def merge_duplicates(fs: list[Finding], cfg: dict[str, Any]) -> list[Finding]:
    if len(fs) < 2:
        return fs
    win, sim_min = int(cfg["line_window"]), float(cfg["min_similarity"])
    sims = cosine_matrix([f.statement for f in fs], [f.statement for f in fs])
    keep: list[Finding] = []
    dropped: set[int] = set()
    for i, f in enumerate(fs):
        if i in dropped:
            continue
        for j in range(i + 1, len(fs)):
            g = fs[j]
            if j in dropped or g.category != f.category or g.anchor.path != f.anchor.path:
                continue
            sa, sb = f.anchor.span(win), g.anchor.span()
            near = (sa is None and sb is None) or (sa and sb and sa[0] <= sb[1] and sb[0] <= sa[1])
            if near and sims[i, j] >= sim_min:
                dropped.add(j)
                for k, v in g.refs.items():
                    if isinstance(v, list):
                        f.refs.setdefault(k, [])
                        f.refs[k] = sorted(set(f.refs[k]) | set(v), key=str)
        keep.append(f)
    return keep

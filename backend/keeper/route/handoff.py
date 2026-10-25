"""A10 hand-offs to another lens (methodology 07 §5): candidates ranked by competence on the fired signals and
by lens distance from the maintainer (the most useful pair may be the two most distant credible lenses)."""

from __future__ import annotations

from typing import Any

import numpy as np

from keeper.core.globs import match
from keeper.core.types import LensItem, RiskSignal


def distance(p_cats: dict[str, int], q_cats: dict[str, int]) -> float:
    keys = sorted(set(p_cats) | set(q_cats))
    if not keys:
        return 0.0
    a = np.array([p_cats.get(k, 0) for k in keys], float)
    b = np.array([q_cats.get(k, 0) for k in keys], float)
    if not a.any() or not b.any():
        return 1.0
    return float(1 - a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def rank_candidates(signals: list[RiskSignal], files: list[str], pool: list[dict[str, Any]],
                    maintainer_cats: dict[str, int], signal_cfg: dict[str, Any], cfg: dict[str, Any]
                    ) -> list[dict[str, Any]]:
    """pool: [{person, items: [LensItem], codeowner: bool, path_findings: int, cats: {category: n}}]."""
    h = cfg["handoff"]
    fired = [s for s in signals if not s.covered] or signals
    out = []
    for c in pool:
        comp = 0.0
        why = []
        for s in fired:
            cats = set(signal_cfg[s.key].get("covering_categories", []) or [])
            items: list[LensItem] = c.get("items", [])
            cover = [it for it in items if it.status == "validated" and it.type == "edge" and
                     (it.category in cats or not cats and it.category in ("security", "build_release")) and
                     any(match(p, g) for p in (s.paths or files) for g in it.triggers.paths)]
            if cover:
                comp += float(h["signal_weights"][s.severity])
                why.append(f"Their lens covers {s.label.lower()}: “{cover[0].title}”")
        if c.get("codeowner"):
            comp += float(h["codeowners_weight"])
            why.append("Owns these paths in CODEOWNERS")
        pf = int(c.get("path_findings", 0))
        if pf >= int(h["min_path_findings"]):
            comp += float(h["path_findings_weight"]) * min(1.0, pf / float(h["path_findings_cap"]))
            why.append(f"Reviewed these files {pf} times")
        if comp <= 0:
            continue
        dist = distance(maintainer_cats, c.get("cats", {}))
        out.append({"person": c["person"], "competence": round(comp, 3), "distance": round(dist, 3),
                    "score": round(comp * (1 + float(h["distance_weight"]) * dist), 3), "why": why})
    return sorted(out, key=lambda x: -x["score"])

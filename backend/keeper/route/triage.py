"""A7 triage: summary and AI-slop signals on content only (methodology 07 §4.1). The prompt and the rules never
see the login, association, account age or contribution counts (G7, test_slop_ignores_author_association)."""

from __future__ import annotations

import re
from typing import Any

from keeper.core.types import PRContext

_IMPORT = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+([\w, ]+)|^\s*import\s+([\w.]+)")


def nonexistent_symbols(ctx: PRContext, known: dict[str, set[str]], package: str | None) -> list[str]:
    """Added lines importing project modules or names that don't exist at the head."""
    out = []
    for path, lines in ctx.added_lines.items():
        if not path.endswith(".py"):
            continue
        for _, text in lines:
            m = _IMPORT.match(text)
            if not m:
                continue
            mod = m.group(1) or m.group(3)
            if package and not (mod == package or mod.startswith(package + ".")):
                continue
            if mod not in known:
                out.append(f"`{mod}` does not exist")
            elif m.group(2):
                for name in (n.strip() for n in m.group(2).split(",")):
                    if name and name not in known[mod] and f"{mod}.{name}" not in known:
                        out.append(f"`{mod}.{name}` does not exist")
    return sorted(set(out))


def whitespace_comment_share(ctx: PRContext) -> float:
    total = trivial = 0
    for lines in ctx.added_lines.values():
        for _, t in lines:
            total += 1
            s = t.strip()
            if not s or s.startswith("#") or s.startswith("<!--"):
                trivial += 1
    return trivial / total if total else 0.0


def slop_rules(ctx: PRContext, known: dict[str, set[str]], package: str | None, cfg: dict[str, Any]
               ) -> tuple[float, list[str]]:
    r = cfg["slop"]["rules"]
    score, ev = 0.0, []
    if any(c.get("conclusion") == "failure" for c in ctx.ci):
        score += float(r["ci_failed"])
        ev.append("CI failed at the head")
    if any("ImportError" in (c.get("summary") or "") or "ModuleNotFoundError" in (c.get("summary") or "")
           for c in ctx.ci):
        score += float(r["import_errors"])
        ev.append("Import errors in CI")
    ns = nonexistent_symbols(ctx, known, package)
    if ns:
        score += float(r["nonexistent_symbols"])
        ev.extend(f"References {x[1:x.index('`', 1)]}, which doesn't exist" for x in ns[:3])
    if whitespace_comment_share(ctx) >= float(cfg["slop"].get("whitespace_comment_share_min", 0.5)):
        score += float(r["whitespace_comment_share"])
        ev.append("Mostly whitespace or comment changes")
    return min(1.0, score), ev


def combine(model_score: float, rules_score: float, cfg: dict[str, Any]) -> float:
    s = cfg["slop"]
    return max(0.0, min(1.0, float(s["model_weight"]) * model_score + float(s["rules_weight"]) * rules_score))


async def triage(ctx_no_author: PRContext, block_no_author: str, symbol_summary: str, known: dict[str, set[str]],
                 package: str | None, cfg: dict[str, Any], *, gateway: Any, job_id: str | None = None
                 ) -> dict[str, Any]:
    res = await gateway.call("triage_signals", {"context_block": block_no_author, "symbol_summary": symbol_summary,
                                                "_sim": {"ctx": ctx_no_author.model_dump(mode="json"),
                                                         "known": {k: sorted(v) for k, v in known.items()},
                                                         "package": package}},
                             job_id=job_id, feature="queue")
    d = res.data
    rules, rule_ev = slop_rules(ctx_no_author, known, package, cfg)
    final = combine(float(d["slop"]["score"]), rules, cfg)
    return {"summary": d["summary"], "slop": {"model": float(d["slop"]["score"]), "rules": rules, "score": round(final, 3),
                                              "evidence": (d["slop"].get("evidence") or []) + rule_ev,
                                              "is_slop": final >= float(cfg["slop"]["threshold"])},
            "description_matches_diff": d.get("description_matches_diff", True),
            "touches_public_api": d.get("touches_public_api", False), "model": res.meta()}

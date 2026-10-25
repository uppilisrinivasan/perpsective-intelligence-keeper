"""The long-context history digest used by lens recall (methodology 05 §3 step 10): one compact line per
substantive finding of the person before the cutoff."""

from __future__ import annotations

from datetime import datetime

from keeper.core.types import Finding, LensItem


def line(f: Finding, item_of: dict[str, str]) -> str:
    a = f.anchor
    where = f"{a.path}:{a.start_line}" if a.path and a.start_line else (a.path or "PR")
    st = f.statement.replace('"', "'")
    tail = f" (item {item_of[f.id]})" if f.id in item_of else ""
    return f'[{f.id}] #{f.pr_number} {where} {f.category} {f.severity} "{st}"{tail}'


def build(findings: list[Finding], items: list[LensItem]) -> str:
    item_of = {fid: it.id for it in items for fid in it.member_ids}
    rows = sorted((f for f in findings if f.substantive), key=lambda f: (f.created_at or datetime.min, f.id))
    return "\n".join(line(f, item_of) for f in rows)


def filter_before(digest: str, created: dict[str, datetime], before: datetime) -> list[str]:
    """Digest lines whose finding predates `before` (no leakage into a later PR's recall)."""
    out = []
    for ln in digest.splitlines():
        fid = ln[1:ln.index("]")] if ln.startswith("[") and "]" in ln else None
        if fid and fid in created and created[fid] < before:
            out.append(ln)
    return out

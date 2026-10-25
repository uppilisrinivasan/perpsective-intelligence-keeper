"""Anchors: human anchors from review-comment fields; model anchors validated and snapped to the diff (01 §2.1)."""

from __future__ import annotations

from keeper.core.types import Anchor, PRContext


def human_anchor(path: str | None, line: int | None, start_line: int | None, side: str | None,
                 original_line: int | None, subject_type: str | None) -> Anchor:
    """The line at the commit the comment was written on (original_line): that is the situation the person
    reviewed. GitHub's `line` follows later pushes, and is null once the comment is outdated."""
    if not path:
        return Anchor(scope="pr")
    if subject_type == "file":
        return Anchor(scope="file", path=path)
    ln = original_line if original_line is not None else line
    if ln is None:
        return Anchor(scope="file", path=path)
    return Anchor(scope="line", path=path, side="LEFT" if side == "LEFT" else "RIGHT",
                  start_line=start_line or ln, end_line=ln)


def snap(ctx: PRContext, path: str | None, start: int | None, end: int | None, snap_lines: int) -> Anchor:
    """Validate a model's anchor against the diff: inside a hunk stays; within snap_lines snaps; else file."""
    if not path:
        return Anchor(scope="pr")
    known = {f.path for f in ctx.files}
    if path not in known:
        match = [p for p in known if p.endswith("/" + path) or path.endswith("/" + p)]
        if len(match) != 1:
            return Anchor(scope="pr")
        path = match[0]
    if start is None:
        return Anchor(scope="file", path=path)
    end = end if end is not None and end >= start else start
    for lo, hi in ctx.hunks.get(path, []):
        if lo <= start <= hi:
            return Anchor(scope="line", path=path, start_line=start, end_line=min(end, hi))
    best = None
    for lo, hi in ctx.hunks.get(path, []):
        d = lo - start if start < lo else start - hi
        if 0 < d <= snap_lines and (best is None or d < best[0]):
            best = (d, lo if start < lo else hi)
    if best is not None:
        return Anchor(scope="line", path=path, start_line=best[1], end_line=best[1])
    return Anchor(scope="file", path=path)

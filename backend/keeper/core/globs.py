"""Path globs with `**` (any depth) and `*` (one segment, or anything for bare file patterns)."""

from __future__ import annotations

import fnmatch
import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def _rx(pattern: str) -> re.Pattern[str]:
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def match(path: str, pattern: str) -> bool:
    if "/" not in pattern:
        return fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pattern) or fnmatch.fnmatchcase(path, pattern)
    return bool(_rx(pattern).match(path))


def match_any(path: str, patterns: list[str]) -> bool:
    return any(match(path, p) for p in patterns)


def area_of(path: str, depth: int) -> str:
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    return "/".join(parts[:depth]) if len(parts) > depth else "/".join(parts[:-1])

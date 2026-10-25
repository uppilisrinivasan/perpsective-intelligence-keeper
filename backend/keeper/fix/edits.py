"""Applying a model's planned edits (methodology 08 §3.4). Each `search` must occur exactly once; new files may
not overwrite; paths stay inside the workspace; build, CI and dependency files are off-limits; tests may be added
but never deleted, skipped or weakened."""

from __future__ import annotations

import difflib
import re
from pathlib import PurePosixPath
from typing import Any

from keeper.core.globs import match_any

_SKIP = re.compile(r"@pytest\.mark\.skip|pytest\.skip\(|@unittest\.skip|^\s*#\s*def test_", re.M)


def safe_path(p: str) -> bool:
    pp = PurePosixPath(p)
    return bool(p) and not pp.is_absolute() and ".." not in pp.parts and not p.startswith((".git/", ".keeper/"))


def forbidden(path: str, routing: dict[str, Any]) -> bool:
    sig = routing["signals"]
    globs = list(sig["build_script_changed"]["build_paths"]) + list(sig["ci_workflow_changed"]["paths"]) + \
        list(routing.get("dependency_files", [])) + ["pyproject.toml"]
    return match_any(path, globs)


def closest(text: str, search: str) -> str:
    first = search.strip("\n").split("\n")[0].strip()
    lines = text.split("\n")
    best = difflib.get_close_matches(first, [ln.strip() for ln in lines], n=1, cutoff=0.4)
    if not best:
        return "no similar line"
    i = [ln.strip() for ln in lines].index(best[0])
    return f"closest match at line {i + 1}: {lines[i].strip()[:120]}"


def apply(files: dict[str, str | None], plan: dict[str, Any], routing: dict[str, Any], test_glob: str
          ) -> tuple[dict[str, str], list[str]]:
    """files: current text by path (None = missing). Returns (changed files, errors)."""
    changed: dict[str, str] = {}
    errors: list[str] = []
    for e in plan.get("edits", []):
        path = e.get("path", "")
        if not safe_path(path):
            errors.append(f"refused path {path!r}")
            continue
        if forbidden(path, routing):
            errors.append(f"{path}: Keeper never edits build, CI or dependency files")
            continue
        cur = changed.get(path, files.get(path))
        if cur is None:
            errors.append(f"{path}: file not found")
            continue
        n = cur.count(e["search"])
        if n != 1:
            errors.append(f"search text {'not found' if n == 0 else f'found {n} times'} in {path}; {closest(cur, e['search'])}")
            continue
        new = cur.replace(e["search"], e["replace"], 1)
        if path.startswith("tests/") and _weakens_tests(cur, new):
            errors.append(f"{path}: the edit removes or skips tests")
            continue
        changed[path] = new
    for nf in plan.get("new_files", []):
        path = nf.get("path", "")
        if not safe_path(path) or forbidden(path, routing):
            errors.append(f"refused new file {path!r}")
            continue
        if files.get(path) is not None or path in changed:
            errors.append(f"{path}: new files may not overwrite existing files")
            continue
        if path.startswith("tests/") and not match_any(path, [test_glob]):
            errors.append(f"{path}: tests must live under tests/")
            continue
        changed[path] = nf["content"]
    return changed, errors


def _weakens_tests(old: str, new: str) -> bool:
    count = lambda t: len(re.findall(r"^\s*def test_", t, re.M))  # noqa: E731
    return count(new) < count(old) or len(_SKIP.findall(new)) > len(_SKIP.findall(old))


def unified(path: str, before: str | None, after: str | None) -> str:
    a = (before or "").splitlines(keepends=True)
    b = (after or "").splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile=f"a/{path}" if before is not None else "/dev/null",
                                        tofile=f"b/{path}" if after is not None else "/dev/null"))


def diff_stats(diff: str) -> dict[str, int]:
    add = sum(1 for ln in diff.split("\n") if ln.startswith("+") and not ln.startswith("+++"))
    rem = sum(1 for ln in diff.split("\n") if ln.startswith("-") and not ln.startswith("---"))
    files = sum(1 for ln in diff.split("\n") if ln.startswith("+++ "))
    return {"additions": add, "deletions": rem, "files": files, "changed_lines": add + rem}


def changed_lines(before: str | None, after: str) -> set[int]:
    sm = difflib.SequenceMatcher(None, (before or "").split("\n"), after.split("\n"))
    out: set[int] = set()
    for tag, _, _, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
    return out

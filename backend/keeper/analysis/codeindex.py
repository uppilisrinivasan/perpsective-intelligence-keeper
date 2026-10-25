"""Symbols per file at a commit (Python `ast`), cached per SHA. Used for the fix planner's repository map, slop
detection (references to symbols that don't exist), `touches_public_api` and mapping tests to areas."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from keeper.config import get_settings
from keeper.sources import git as G


def _symbols(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"symbols": [], "imports": [], "all": None, "error": "syntax"}
    syms, imports, all_ = [], [], None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            syms.append({"name": node.name, "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                         "line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno),
                         "public": not node.name.startswith("_")})
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    if t.id == "__all__" and isinstance(node.value, ast.List | ast.Tuple):
                        all_ = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                    else:
                        syms.append({"name": t.id, "kind": "variable", "line": node.lineno,
                                     "end_line": node.lineno, "public": not t.id.startswith("_")})
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return {"symbols": syms, "imports": imports, "all": all_}


def build(repo_path: Path, sha: str) -> dict[str, Any]:
    cache = get_settings().runtime_dir / "cache" / "codeindex"
    f = cache / f"{sha}.json"
    if f.exists():
        return json.loads(f.read_text())
    paths = [p for p in G.ls_tree(repo_path, sha) if p.endswith(".py")]
    texts = G.read_many(repo_path, sha, paths)
    idx = {p: _symbols(t) for p, t in texts.items() if t is not None}
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(idx))
    return idx


def module_name(path: str) -> str:
    p = path[:-3] if path.endswith(".py") else path
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")


def known_symbols(idx: dict[str, Any]) -> dict[str, set[str]]:
    """module name → top-level names it defines (for checking `from x import y` and `x.y`)."""
    out: dict[str, set[str]] = {}
    for path, info in idx.items():
        out[module_name(path)] = {s["name"] for s in info.get("symbols", [])}
    return out


def summary(idx: dict[str, Any], max_chars: int = 4000) -> str:
    lines = []
    for path in sorted(idx):
        names = [s["name"] for s in idx[path].get("symbols", []) if s["public"] and s["kind"] != "variable"]
        if names:
            lines.append(f"{module_name(path)}: {', '.join(names[:12])}")
    return "\n".join(lines)[:max_chars]

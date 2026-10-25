"""Repository policy files: CODEOWNERS, MAINTAINERS, CONTRIBUTING (review notes), pyproject dependencies."""

from __future__ import annotations

import fnmatch
import re
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def parse_codeowners(text: str | None) -> list[tuple[str, list[str]]]:
    rules = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split()
        rules.append((parts[0], [p.lstrip("@") for p in parts[1:] if p.startswith("@")]))
    return rules


def codeowners_for(rules: list[tuple[str, list[str]]], path: str) -> list[str]:
    owners: list[str] = []
    for pattern, who in rules:  # last match wins, as on GitHub
        if _co_match(pattern, path):
            owners = who
    return owners


def _co_match(pattern: str, path: str) -> bool:
    if pattern == "*":
        return True
    p = pattern.lstrip("/")
    if p.endswith("/"):
        return path.startswith(p) if pattern.startswith("/") else ("/" + path).find("/" + p) >= 0
    return fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, p + "/*") or path.startswith(p.rstrip("*"))


def parse_maintainers(text: str | None) -> list[str]:
    return re.findall(r"@([A-Za-z0-9][A-Za-z0-9-]*(?:\[bot\])?)", text or "")


def review_notes(text: str | None, heading_regex: str, max_chars: int) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    out, on = [], False
    rx = re.compile(heading_regex)
    for ln in lines:
        if ln.startswith("#"):
            on = bool(rx.match(ln))
            if on:
                out.append(ln)
            continue
        if on:
            out.append(ln)
    return "\n".join(out).strip()[:max_chars]


def pyproject_dependencies(text: str | None) -> dict[str, Any]:
    if not text or tomllib is None:
        return {"dependencies": [], "optional": {}, "build_system": {}, "sections": []}
    try:
        d = tomllib.loads(text)
    except Exception:
        return {"dependencies": [], "optional": {}, "build_system": {}, "sections": []}
    proj = d.get("project", {})
    sections = []
    for k, v in d.items():
        sections.append(k)
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict):
                    sections.append(f"{k}.{k2}")
                    for k3 in v2:
                        if isinstance(v2[k3], dict):
                            sections.append(f"{k}.{k2}.{k3}")
    return {"dependencies": list(proj.get("dependencies", []) or []),
            "optional": dict(proj.get("optional-dependencies", {}) or {}), "build_system": d.get("build-system", {}),
            "scripts": proj.get("scripts", {}), "sections": sections}


def dep_name(spec: str) -> tuple[str, str | None]:
    m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*(==\s*([^,;\s]+)|>=\s*([^,;\s]+))?", spec)
    if not m:
        return spec.strip(), None
    return m.group(1).lower(), (m.group(3) or m.group(4))

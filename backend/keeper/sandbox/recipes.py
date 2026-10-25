"""Recipe commands from config/sandbox.yaml. Models never supply commands: only these templates run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from keeper.config import get_config, get_settings
from keeper.core.errors import SandboxUnavailable


def recipes() -> dict[str, Any]:
    return get_config().sandbox["recipes"]


def detect(repo_files: list[str]) -> str | None:
    for name, r in recipes().items():
        if any(f in repo_files for f in r.get("detect", [])):
            return name
    return None


def command(recipe: dict[str, Any], key: str, *, python: str, tests: list[str] | None = None,
            files: list[str] | None = None) -> list[str]:
    """Fill a recipe command template. `{tests}` and `{files}` expand to validated relative paths only."""
    out: list[str] = []
    for part in recipe[key]:
        if part == "{tests}":
            out.extend(_safe_paths(tests or []))
        elif part == "{files}":
            out.extend(_safe_paths(files or []))
        else:
            out.append(part.replace("{python}", python))
    return out


def _safe_paths(paths: list[str]) -> list[str]:
    ok = []
    for p in paths:
        if p.startswith(("-", "/")) or ".." in Path(p).parts or "\x00" in p:
            raise SandboxUnavailable(f"refusing an unsafe path argument: {p!r}")
        ok.append(p)
    return ok


def wheelhouse(recipe: dict[str, Any]) -> Path:
    return get_settings().path(recipe["wheelhouse"])

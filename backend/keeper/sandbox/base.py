"""The sandbox interface (docs/04-architecture/05-sandbox-runners.md §1). Commands come only from recipes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Availability:
    ok: bool
    reason: str | None = None


@dataclass
class Workspace:
    id: str
    path: Path
    sha: str
    recipe: str
    python: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    id: str
    path: Path
    workspace: Workspace


@dataclass
class RunResult:
    exit_code: int
    stdout_tail: str
    stderr_tail: str
    duration_ms: int
    timed_out: bool = False
    artefacts: dict[str, Path] = field(default_factory=dict)


@dataclass
class FileChange:
    path: str
    content: str | None  # None deletes


class SandboxRunner(Protocol):
    name: str
    isolation: str

    async def available(self) -> Availability: ...
    async def prepare(self, repo_path: Path, sha: str, recipe: dict[str, Any], recipe_name: str) -> Workspace: ...
    async def checkpoint(self, ws: Workspace) -> Checkpoint: ...
    async def branch(self, cp: Checkpoint) -> Workspace: ...
    async def write_files(self, ws: Workspace, changes: list[FileChange]) -> None: ...
    async def read_file(self, ws: Workspace, path: str) -> str | None: ...
    async def run(self, ws: Workspace, cmd: list[str], *, timeout: int,
                  on_output: Callable[[str], None] | None = None) -> RunResult: ...
    async def dispose(self, ws: Workspace) -> None: ...

"""Docker runner: workspaces and checkpoints on the host (as local); only execution happens in the container,
with no network, CPU and memory limits, read-only root and the wheelhouse mounted read-only."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from keeper.sandbox.base import Availability, RunResult, Workspace
from keeper.sandbox.local import LocalRunner


class DockerRunner(LocalRunner):
    name = "docker"

    def __init__(self) -> None:
        super().__init__()
        self.isolation = "Docker: tests run in a container with no network, 2 CPUs and 2 GB of memory."
        self.image = "python:3.12-slim"

    async def available(self) -> Availability:
        if not shutil.which("docker"):
            return Availability(False, "Docker is not installed")
        r = await asyncio.to_thread(subprocess.run, ["docker", "info", "--format", "{{.ServerVersion}}"],
                                    capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return Availability(False, "the Docker daemon is not running")
        return Availability(True, None)

    def venv_for(self, recipe: dict[str, Any], recipe_name: str) -> str:
        self.image = recipe.get("image", self.image)
        self._wheelhouse = str(Path(recipe["wheelhouse"]).resolve())
        return "python"

    async def run(self, ws: Workspace, cmd: list[str], *, timeout: int,
                  on_output: Callable[[str], None] | None = None) -> RunResult:
        inner = " ".join(["pip", "install", "-q", "--no-index", "--find-links", "/wheels", "pytest", "ruff", "&&",
                          *[c.replace(str(ws.path), "/work") for c in cmd]])
        docker = ["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
                  "-e", "PYTHONPATH=/work", "-e", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1", "-v", f"{ws.path}:/work",
                  "-v", f"{self._wheelhouse}:/wheels:ro", "-w", "/work", self.image, "sh", "-c", inner]
        saved, self.wrapper = self.wrapper, []
        try:
            return await LocalRunner.run(self, ws, docker, timeout=timeout, on_output=on_output)
        finally:
            self.wrapper = saved

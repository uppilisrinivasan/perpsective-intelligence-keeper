"""The local runner: always available, best-effort isolation (temp copy, separate venv, allow-listed env,
resource limits, process-group kill on timeout, network denied with sandbox-exec or unshare when present)."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from keeper.config import get_config, get_settings
from keeper.core.errors import SandboxUnavailable
from keeper.sandbox.base import Availability, Checkpoint, FileChange, RunResult, Workspace
from keeper.sandbox.recipes import wheelhouse
from keeper.sources import git as G


def _net_wrapper() -> tuple[list[str], str]:
    cfg = get_config().sandbox
    if cfg.get("network", "off") != "off":
        return [], "network allowed by configuration"
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        prof = get_settings().path(cfg.get("macos_profile", "config/sandbox/macos-deny-network.sb"))
        if prof.exists():
            r = subprocess.run(["sandbox-exec", "-f", str(prof), "/usr/bin/true"], capture_output=True)
            if r.returncode == 0:
                return ["sandbox-exec", "-f", str(prof)], "network denied (sandbox-exec)"
    if platform.system() == "Linux" and shutil.which("unshare"):
        r = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
        if r.returncode == 0:
            return ["unshare", "-rn"], "network denied (unshare)"
    return [], "no network isolation available on this machine"


def _limits() -> Callable[[], None]:
    lim = get_config().sandbox.get("limits", {})

    def apply() -> None:
        os.setsid()
        try:
            import resource
            cpu = int(lim.get("cpu_seconds", 300))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            files = int(lim.get("open_files", 512))
            resource.setrlimit(resource.RLIMIT_NOFILE, (files, files))
            if platform.system() == "Linux":
                mem = int(lim.get("address_space_mb", 2048)) * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        except Exception:
            pass
    return apply


class LocalRunner:
    name = "local"

    def __init__(self) -> None:
        self.root = get_settings().runtime_dir / "sandboxes"
        self.wrapper, self.net_note = _net_wrapper()
        self.isolation = f"Local sandbox: tests run on this machine with limited isolation ({self.net_note})."

    async def available(self) -> Availability:
        return Availability(True, None)

    def venv_for(self, recipe: dict[str, Any], recipe_name: str) -> str:
        """One virtual environment per recipe, built offline from the wheelhouse (trusted, pinned wheels)."""
        wh = wheelhouse(recipe)
        key = hashlib.sha256((recipe_name + ",".join(recipe.get("venv_packages", []))).encode()).hexdigest()[:10]
        venv = self.root / "_venvs" / f"{recipe_name}-{key}"
        py = venv / "bin" / "python"
        if py.exists():
            return str(py)
        if not wh.exists() or not any(wh.glob("*.whl")):
            raise SandboxUnavailable("The test wheelhouse is missing (fixes need it offline). Run ./run.sh once "
                                     "while online to download it.", {"wheelhouse": str(wh)})
        venv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
        r = subprocess.run([str(py), "-m", "pip", "install", "-q", "--no-index", "--find-links", str(wh),
                            *recipe.get("venv_packages", [])], capture_output=True, text=True)
        if r.returncode != 0:
            shutil.rmtree(venv, ignore_errors=True)
            raise SandboxUnavailable(f"Couldn't set up the test environment: {r.stderr[-300:]}")
        return str(py)

    async def prepare(self, repo_path: Path, sha: str, recipe: dict[str, Any], recipe_name: str) -> Workspace:
        wid = f"sbx_{uuid.uuid4().hex[:10]}"
        path = self.root / wid / "ws"
        await asyncio.to_thread(G.export_tree, repo_path, sha, path)
        (path / ".keeper").mkdir(exist_ok=True)
        py = await asyncio.to_thread(self.venv_for, recipe, recipe_name)
        return Workspace(id=wid, path=path, sha=sha, recipe=recipe_name, python=py)

    async def checkpoint(self, ws: Workspace) -> Checkpoint:
        cid = f"{ws.id}-cp{uuid.uuid4().hex[:4]}"
        dest = self.root / ws.id / cid
        await asyncio.to_thread(shutil.copytree, ws.path, dest, symlinks=True)
        return Checkpoint(id=cid, path=dest, workspace=ws)

    async def branch(self, cp: Checkpoint) -> Workspace:
        wid = f"{cp.workspace.id}-{uuid.uuid4().hex[:6]}"
        dest = self.root / cp.workspace.id / wid
        await asyncio.to_thread(shutil.copytree, cp.path, dest, symlinks=True)
        return Workspace(id=wid, path=dest, sha=cp.workspace.sha, recipe=cp.workspace.recipe,
                         python=cp.workspace.python, meta={"root": cp.workspace.id})

    def _inside(self, ws: Workspace, rel: str) -> Path:
        p = (ws.path / rel).resolve()
        if ws.path.resolve() not in p.parents and p != ws.path.resolve():
            raise SandboxUnavailable(f"path outside the workspace: {rel}")
        return p

    async def write_files(self, ws: Workspace, changes: list[FileChange]) -> None:
        for ch in changes:
            p = self._inside(ws, ch.path)
            if ch.content is None:
                if p.exists():
                    p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ch.content, encoding="utf-8")

    async def read_file(self, ws: Workspace, path: str) -> str | None:
        p = self._inside(ws, path)
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None

    def env(self, ws: Workspace) -> dict[str, str]:
        allow = get_config().sandbox.get("env_allowlist", ["PATH", "LANG"])
        env = {k: os.environ[k] for k in allow if k in os.environ}
        home = ws.path.parent / ".home"
        home.mkdir(exist_ok=True)
        env.update({"HOME": str(home), "PYTHONPATH": str(ws.path), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TMPDIR": str(home)})
        return env

    async def run(self, ws: Workspace, cmd: list[str], *, timeout: int,
                  on_output: Callable[[str], None] | None = None) -> RunResult:
        t0 = time.perf_counter()
        argv = self.wrapper + cmd
        proc = await asyncio.create_subprocess_exec(*argv, cwd=str(ws.path), env=self.env(ws),
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                    preexec_fn=_limits())
        chunks: list[str] = []
        timed_out = False

        async def pump() -> None:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                chunks.append(text)
                if on_output:
                    on_output(text)
        try:
            await asyncio.wait_for(asyncio.gather(pump(), proc.wait()), timeout=timeout)
        except TimeoutError:
            timed_out = True
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
        out = "".join(chunks)
        arts = {p.name: p for p in (ws.path / ".keeper").glob("*.xml")}
        return RunResult(exit_code=proc.returncode if proc.returncode is not None else -9, stdout_tail=out[-20000:],
                         stderr_tail="", duration_ms=int((time.perf_counter() - t0) * 1000), timed_out=timed_out,
                         artefacts=arts)

    async def dispose(self, ws: Workspace) -> None:
        if get_settings().KEEPER_KEEP_SANDBOXES:
            return
        root = self.root / (ws.meta.get("root") or ws.id)
        await asyncio.to_thread(shutil.rmtree, root, True)

    def janitor(self) -> int:
        hours = float(get_config().sandbox.get("janitor_hours", 24))
        n = 0
        if not self.root.exists():
            return 0
        for d in self.root.iterdir():
            if d.name.startswith("sbx_") and time.time() - d.stat().st_mtime > hours * 3600:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n

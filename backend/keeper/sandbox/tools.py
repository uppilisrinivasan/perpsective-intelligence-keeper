"""Static tools (ruff, bandit) over untrusted code: they parse, never execute it, but still run through the
sandbox module with an allow-listed environment and a timeout (only keeper.sandbox spawns tools on PR code)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _bin(name: str) -> str | None:
    cand = Path(sys.executable).parent / name
    return str(cand) if cand.exists() else shutil.which(name)


def version(name: str) -> str:
    b = _bin(name)
    if not b:
        return "missing"
    r = subprocess.run([b, "--version"], capture_output=True, text=True, timeout=20)
    return (r.stdout or r.stderr).strip().split("\n")[0]


def run_static(files: dict[str, str], *, ruff_select: list[str], bandit: bool, ruff: bool,
               timeout: int = 60) -> dict[str, list[dict[str, Any]]]:
    """Run ruff and bandit on the given {path: text} in a temp tree. Returns {"ruff": [...], "bandit": [...]}."""
    out: dict[str, list[dict[str, Any]]] = {"ruff": [], "bandit": []}
    py = [p for p in files if p.endswith(".py")]
    if not py:
        return out
    with tempfile.TemporaryDirectory(prefix="keeper-static-") as tmp:
        for p, text in files.items():
            dest = Path(tmp) / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "LANG": "C.UTF-8"}
        if ruff and (rb := _bin("ruff")):
            r = subprocess.run([rb, "check", "--select", ",".join(ruff_select), "--output-format", "json",
                                "--no-cache", "--exit-zero", *py], cwd=tmp, capture_output=True, text=True, env=env,
                               timeout=timeout)
            try:
                for d in json.loads(r.stdout or "[]"):
                    out["ruff"].append({"path": os.path.relpath(d["filename"], tmp), "line": d["location"]["row"],
                                        "end_line": (d.get("end_location") or {}).get("row"), "code": d["code"],
                                        "message": d["message"]})
            except json.JSONDecodeError:
                pass
        if bandit and (bb := _bin("bandit")):
            r = subprocess.run([bb, "-f", "json", "-q", *py], cwd=tmp, capture_output=True, text=True, env=env,
                               timeout=timeout)
            try:
                for d in json.loads(r.stdout or "{}").get("results", []):
                    out["bandit"].append({"path": os.path.relpath(os.path.join(tmp, d["filename"]), tmp)
                                          if not os.path.isabs(d["filename"]) else os.path.relpath(d["filename"], tmp),
                                          "line": d["line_number"], "code": d["test_id"],
                                          "severity": d["issue_severity"], "message": d["issue_text"]})
            except json.JSONDecodeError:
                pass
    return out

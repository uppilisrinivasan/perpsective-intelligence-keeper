"""python -m keeper.cli check | data-line | eval (used by run.sh --check and --eval)."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import socket
import sys
from pathlib import Path

SECRET_RE = re.compile(r"""(?i)\b(api[_-]?key|secret|token|password)\b["']?\s*[:=]\s*["']([A-Za-z0-9_\-/+]{24,})["']""")
SCAN_DIRS = ("config", "backend/keeper", "frontend/src", "docs", "data/sources/keeper")
SCAN_EXT = {".py", ".ts", ".tsx", ".yaml", ".yml", ".json", ".md", ".toml"}


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _bad(msg: str) -> None:
    print(f"  ✗ {msg}")


def _info(msg: str) -> None:
    print(f"  · {msg}")


def secret_scan(root: Path) -> list[str]:
    hits = []
    for d in SCAN_DIRS:
        for f in (root / d).rglob("*"):
            if not f.is_file() or f.suffix not in SCAN_EXT or "node_modules" in f.parts or f.stat().st_size > 2_000_000:
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in SECRET_RE.finditer(text):
                val = m.group(2)
                if val.startswith("${") or "example" in val.lower() or re.fullmatch(r"[a-z_.]+", val):
                    continue
                hits.append(str(f.relative_to(root)))
                break
    return hits


def cmd_check(a: argparse.Namespace) -> int:
    from keeper.config import get_settings
    from keeper.config.loader import load_config
    from keeper.config.settings import StartupError, validate_startup
    from keeper.datagen.validate import verify_manifest
    from keeper.llm.prompts import check_lock

    errors = 0
    try:
        s = get_settings()
        for w in validate_startup(s):
            _info(w)
        _ok(".env is valid")
    except (StartupError, ValueError) as e:
        _bad(f".env: {e}")
        return 1
    try:
        load_config(validate=True)
        _ok("config/ matches its schemas")
    except Exception as e:  # noqa: BLE001
        _bad(f"config: {e}")
        errors += 1
    drift = check_lock()
    if drift:
        _bad("prompts changed without a version bump: " + ", ".join(drift[:5]))
        errors += 1
    else:
        _ok("prompts match config/prompts/versions.lock")
    problems = verify_manifest(s.data_dir)
    if problems:
        _bad(f"data/ doesn't match the manifest ({len(problems)}): " + "; ".join(problems[:3]))
        errors += 1
    else:
        m = json.loads((s.data_dir / "manifest.json").read_text())
        snap = (s.data_dir / "snapshots").exists()
        _ok(f"data/ verified ({len(m.get('files', {}))} files)" + ("" if snap else "; no saved results yet"))
    if s.LLM_PROVIDER == "fake":
        _info("LLM_PROVIDER=fake: offline simulator, no model probe")
    elif s.api_key:
        from keeper.llm import probe
        from keeper.llm.gateway import get_gateway
        res = asyncio.run(get_gateway().run_probe())
        probe.save(res)
        for mid, st in res.get("models", {}).items():
            (_ok if st.get("exists") == "available" and st.get("chat") == "ok" else _bad)(
                f"model {mid}: {st.get('exists')}, chat {st.get('chat')}, tools {st.get('tools')}")
    else:
        _info("No API key: saved-results mode (the probe is skipped)")
    from keeper.sandbox.select import select
    runner, reason, want = asyncio.run(select())
    (_info if reason else _ok)(f"sandbox: {runner.name}" + (f" (asked for {want}: {reason})" if reason else ""))
    hits = secret_scan(s.path("."))
    if hits:
        _bad("possible secrets in: " + ", ".join(hits[:5]))
        errors += 1
    else:
        _ok("no secrets found outside .env")
    sock = socket.socket()
    try:
        sock.bind((s.APP_HOST, int(a.port or s.APP_PORT)))
        _ok(f"port {a.port or s.APP_PORT} is free")
    except OSError:
        _info(f"port {a.port or s.APP_PORT} is in use (Keeper may already be running)")
    finally:
        sock.close()
    return 1 if errors else 0


def cmd_data_line(a: argparse.Namespace) -> int:
    from keeper.config import get_settings
    from keeper.datagen.validate import verify_manifest
    s = get_settings()
    mf = s.data_dir / "manifest.json"
    if not mf.exists():
        print("· No data/manifest.json")
        return 0
    problems = verify_manifest(s.data_dir)
    import hashlib
    sha = hashlib.sha256(mf.read_bytes()).hexdigest()[:4]
    size = sum(f.stat().st_size for f in s.data_dir.rglob("*") if f.is_file()) / 1e6
    print(f"✓ Data verified (manifest {sha}…, {size:.1f} MB)" if not problems else
          f"✗ Data doesn't match the manifest ({len(problems)} files)")
    return 0


def cmd_eval(a: argparse.Namespace) -> int:
    from keeper.config import get_settings
    from keeper.db.__main__ import upgrade
    from keeper.db.session import session_scope
    from keeper.eval import harness, report
    from keeper.services.common import project

    s = get_settings()
    upgrade()
    with session_scope() as db:
        try:
            p = project(db, None)
        except Exception:  # noqa: BLE001
            from keeper.ingest.demo import load_demo
            p = load_demo(db)
        rep = harness.run(db, p)
    simulated = _simulated(s)
    path = report.write(rep, simulated=simulated)
    print(report.table(rep))
    print(f"\nWritten to {path}" + (" (computed on offline-simulated results)" if simulated else ""))
    return 0 if all(c["pass"] is not False for c in rep["checks"]) else 1


def _simulated(s) -> bool:  # type: ignore[no-untyped-def]
    from keeper.db import repo as R
    snap = R.get_state_cached("snapshot") or {}
    return s.LLM_PROVIDER == "fake" or bool(snap.get("simulated"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="keeper.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--port", type=int)
    sub.add_parser("data-line")
    sub.add_parser("eval")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "data-line": cmd_data_line, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

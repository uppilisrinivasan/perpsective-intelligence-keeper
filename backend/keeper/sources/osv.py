"""OSV.dev vulnerability lookups for new dependencies (no key needed; cached 24 h)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from keeper.config import get_config, get_settings


def _cache_file(name: str, version: str | None):  # type: ignore[no-untyped-def]
    d = get_settings().runtime_dir / "cache" / "osv"
    d.mkdir(parents=True, exist_ok=True)
    return d / (hashlib.sha256(f"{name}=={version}".encode()).hexdigest()[:20] + ".json")


async def query(name: str, version: str | None) -> dict[str, Any]:
    cfg = get_config().routing["osv"]
    f = _cache_file(name, version)
    if f.exists() and time.time() - f.stat().st_mtime < float(cfg["cache_hours"]) * 3600:
        return json.loads(f.read_text())
    body: dict[str, Any] = {"package": {"name": name, "ecosystem": cfg["ecosystem"]}}
    if version:
        body["version"] = version
    try:
        async with httpx.AsyncClient(timeout=float(cfg["timeout_seconds"])) as c:
            r = await c.post(get_settings().OSV_API_URL.rstrip("/") + "/query", json=body)
            r.raise_for_status()
            data = r.json() or {}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "version": version, "vulns": [], "error": f"Vulnerability check unavailable ({type(e).__name__})"}
    vulns = []
    for v in data.get("vulns", [])[:20]:
        url = next((ref["url"] for ref in v.get("references", []) if ref.get("type") in ("ADVISORY", "WEB")), None)
        vulns.append({"id": v.get("id"), "summary": v.get("summary"), "aliases": v.get("aliases", []), "url": url})
    out = {"name": name, "version": version, "vulns": vulns, "error": None}
    f.write_text(json.dumps(out))
    return out

"""Tavily web search for the hand-off note (optional: off without TAVILY_API_KEY; cached 24 h)."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx

from keeper.config import get_config, get_settings


def configured() -> bool:
    return bool(get_settings().TAVILY_API_KEY.get_secret_value())


async def search(query: str) -> dict[str, Any]:
    if not configured():
        return {"status": "not_configured", "results": []}
    cfg = get_config().routing["tavily"]
    d = get_settings().runtime_dir / "cache" / "tavily"
    d.mkdir(parents=True, exist_ok=True)
    f = d / (hashlib.sha256(query.encode()).hexdigest()[:20] + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < float(cfg["cache_hours"]) * 3600:
        return json.loads(f.read_text())
    try:
        async with httpx.AsyncClient(timeout=float(cfg.get("timeout_seconds", 15))) as c:
            r = await c.post(cfg["api_url"] + "/search",
                             headers={"Authorization": f"Bearer {get_settings().TAVILY_API_KEY.get_secret_value()}"},
                             json={"query": query, "search_depth": cfg["search_depth"], "max_results": cfg["max_results"],
                                   "include_answer": False})
            r.raise_for_status()
            data = r.json()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": type(e).__name__, "results": []}
    out = {"status": "ok", "results": [{"title": x.get("title", ""), "url": x.get("url", ""),
                                        "snippet": (x.get("content") or "")[:300]} for x in data.get("results", [])]}
    f.write_text(json.dumps(out))
    return out

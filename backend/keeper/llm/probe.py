"""Capability probe per model ID (gateway §3), cached in .runtime/cache/probe.json for 24 hours."""

from __future__ import annotations

import json
import time
from typing import Any

from keeper.config import get_config, get_settings
from keeper.llm.providers import ProviderError

_TINY_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                "additionalProperties": False}


def _path():
    p = get_settings().runtime_dir / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p / "probe.json"


def load_cached() -> dict[str, Any]:
    f = _path()
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError:
        return {}
    hours = float(get_config().models.get("probe", {}).get("cache_hours", 24))
    if time.time() - data.get("_at", 0) > hours * 3600:
        return {}
    return data


def save(results: dict[str, Any]) -> None:
    results["_at"] = time.time()
    _path().write_text(json.dumps(results, indent=2))


async def probe_model(provider: Any, model_id: str, available: list[str] | None, *, tools: bool,
                      reasoning_params: dict[str, Any]) -> dict[str, Any]:
    r: dict[str, Any] = {"exists": "unknown", "chat": "unknown", "json_schema": "unknown", "json_object": "unknown",
                         "reasoning": "unknown", "tools": "n/a"}
    if available is not None:
        r["exists"] = "available" if model_id in available else "missing"
        if r["exists"] == "missing":
            return r
    msg = [{"role": "user", "content": "Reply with the word ok."}]
    try:
        await provider.complete(model=model_id, messages=msg, params={"max_tokens": 5, "temperature": 0},
                                response_format=None)
        r["chat"] = "ok"
        r["exists"] = "available"
    except ProviderError as e:
        r["chat"] = e.kind
        if e.kind == "missing_model":
            r["exists"] = "missing"
        return r
    jmsg = [{"role": "user", "content": 'Return the JSON object {"ok": true} and nothing else.'}]
    for kind, rf in (("json_schema", {"type": "json_schema", "json_schema": {"name": "probe", "schema": _TINY_SCHEMA,
                                                                              "strict": True}}),
                     ("json_object", {"type": "json_object"})):
        try:
            resp = await provider.complete(model=model_id, messages=jmsg, params={"max_tokens": 40, "temperature": 0},
                                           response_format=rf)
            try:
                from keeper.llm.schemas import parse_json
                ok = parse_json(resp.text).get("ok") is True
                r[kind] = "supported" if ok else "ignored"
            except Exception:
                r[kind] = "ignored"
        except ProviderError:
            r[kind] = "rejected"
    try:
        await provider.complete(model=model_id, messages=msg, params={"max_tokens": 5, **reasoning_params},
                                response_format=None)
        r["reasoning"] = "accepted"
    except ProviderError:
        r["reasoning"] = "rejected"
    if tools:
        tool = [{"type": "function", "function": {"name": "ping", "description": "Ping.",
                                                  "parameters": {"type": "object", "properties": {}}}}]
        try:
            resp = await provider.complete(model=model_id, messages=[{"role": "user", "content": "Call the ping tool."}],
                                           params={"max_tokens": 40, "temperature": 0}, response_format=None,
                                           tools=tool)
            r["tools"] = "supported" if resp.tool_calls else "ignored"
        except ProviderError:
            r["tools"] = "rejected"
    return r


async def run_probe(provider: Any) -> dict[str, Any]:
    cfg = get_config().models
    roles = cfg["roles"]
    try:
        available = await provider.list_models()
    except ProviderError:
        available = None
    results: dict[str, Any] = {"models": {}}
    off = cfg["reasoning_params"]["nemotron"]["off"]
    seen: dict[str, dict[str, Any]] = {}
    for _name, role in roles.items():
        mid = role["model"]
        if mid in seen and not (role.get("tools") and seen[mid].get("tools") == "n/a"):
            continue
        seen[mid] = await probe_model(provider, mid, available, tools=bool(role.get("tools")), reasoning_params=off)
    results["models"] = seen
    save(results)
    return results

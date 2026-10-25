"""LLM output schemas (config/schemas/llm/*.json): load, validate, and describe errors for the repair re-ask."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jsonschema

from keeper.config import get_settings


@lru_cache(maxsize=64)
def load_schema(name: str) -> dict[str, Any]:
    path = get_settings().config_dir / "schemas" / "llm" / f"{name}.json"
    return json.loads(path.read_text())


def validation_errors(name: str, data: Any) -> list[str]:
    schema = load_schema(name)
    v = jsonschema.Draft202012Validator(schema)
    errs = []
    for e in sorted(v.iter_errors(data), key=lambda e: list(e.path))[:12]:
        loc = "/".join(str(p) for p in e.path) or "(root)"
        errs.append(f"{loc}: {e.message[:200]}")
    return errs


def parse_json(text: str) -> Any:
    """Parse model output: strip reasoning blocks and code fences, then take the outermost JSON object."""
    t = text or ""
    while "<think>" in t and "</think>" in t:
        a, b = t.index("<think>"), t.index("</think>")
        t = t[:a] + t[b + len("</think>"):]
    t = t.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            return json.loads(t[a:b + 1])
        raise


def minimal_instance(schema: dict[str, Any]) -> Any:
    """A schema-valid minimal value (the fake provider's default for prompts without a simulator)."""
    if "anyOf" in schema:
        return minimal_instance(schema["anyOf"][-1]) if schema["anyOf"][-1].get("type") == "null" else \
            minimal_instance(schema["anyOf"][0])
    t = schema.get("type")
    if t == "object":
        return {k: minimal_instance(schema["properties"][k]) for k in schema.get("required", [])}
    if t == "array":
        n = schema.get("minItems", 0)
        return [minimal_instance(schema["items"]) for _ in range(n)]
    if t == "string":
        if "enum" in schema:
            return schema["enum"][0]
        return "n/a".ljust(schema.get("minLength", 0), "x")
    if t in ("integer", "number"):
        return schema.get("minimum", 0)
    if t == "boolean":
        return False
    return None

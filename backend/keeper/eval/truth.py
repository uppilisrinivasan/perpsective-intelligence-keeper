"""Read data/ground_truth/ (planted slots, expected lanes, comment labels, outcomes)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from keeper.config import get_settings


def _dir() -> Path:
    return get_settings().data_dir / "ground_truth"


def _jsonl(name: str) -> list[dict[str, Any]]:
    f = _dir() / name
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


def slots() -> dict[str, dict[str, Any]]:
    return json.loads((_dir() / "slots.json").read_text())


def pr_slots() -> list[dict[str, Any]]:
    return _jsonl("pr_slots.jsonl")


def pr_lanes() -> list[dict[str, Any]]:
    return _jsonl("pr_lanes.jsonl")


def comments() -> list[dict[str, Any]]:
    return _jsonl("comment_truth.jsonl")


def outcomes() -> list[dict[str, Any]]:
    return _jsonl("outcomes.jsonl")


def thresholds() -> dict[str, Any]:
    f = _dir() / "eval_thresholds.json"
    return json.loads(f.read_text()) if f.exists() else {}

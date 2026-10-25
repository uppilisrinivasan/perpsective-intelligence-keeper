"""Load the scenario (with its profile), the world values and the slot checks."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from keeper.config import get_settings


def _merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


@dataclass
class World:
    scenario: dict[str, Any]
    world: dict[str, Any]
    slot_checks: dict[str, Any]
    profile: str
    seed: int
    dir: Path

    @property
    def project(self) -> dict[str, Any]:
        return self.world["project"]

    @property
    def pkg(self) -> str:
        return str(self.project["package"])

    def slot(self, sid: str) -> dict[str, Any]:
        return next(s for s in self.scenario["concern_slots"] if s["id"] == sid)

    def sha256(self) -> str:
        blob = json.dumps({"scenario": self.scenario, "world": self.world, "seed": self.seed}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()


def datagen_dir() -> Path:
    return get_settings().config_dir / "datagen"


def load_world(profile: str | None = None, seed: int | None = None) -> World:
    d = datagen_dir()
    scenario = yaml.safe_load((d / "scenario.yaml").read_text(encoding="utf-8"))
    s = get_settings()
    prof = profile or s.DATAGEN_PROFILE or scenario.get("profile", "full")
    pf = d / "profiles" / f"{prof}.yaml"
    if pf.exists():
        scenario = _merge(scenario, yaml.safe_load(pf.read_text(encoding="utf-8")) or {})
    scenario["profile"] = prof
    world = yaml.safe_load((d / "world.yaml").read_text(encoding="utf-8"))
    checks = yaml.safe_load((d / "slot_checks.yaml").read_text(encoding="utf-8"))
    return World(scenario=scenario, world=world, slot_checks=checks, profile=prof,
                 seed=int(seed if seed is not None else s.DATAGEN_SEED or scenario["seed"]), dir=d)

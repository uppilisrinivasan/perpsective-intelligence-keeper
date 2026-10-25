"""Load and validate `config/*.yaml` (docs/07-configuration/03-config-files.md).

Values may reference environment variables as `${VAR:-default}` (nested defaults allowed). The environment is the
process environment over `.env`. Code never repeats these defaults: it reads them from the loaded config.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from keeper.config.settings import ENV_FILE, get_settings

CONFIG_FILES = [
    "models", "pricing", "taxonomy", "context", "baseline", "matching", "lens", "routing", "review", "fix",
    "sandbox", "find", "fidelity", "growth", "eval", "datasets", "redaction", "glossary", "ui", "ingest",
]

_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::-((?:[^{}]|\{[^{}]*\})*))?\}")


def read_dotenv(path: Path = ENV_FILE) -> dict[str, str]:
    """A minimal KEY=VALUE parser (no shell evaluation). Comments and blank lines are skipped."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].rstrip()
        out[key] = val
    return out


def environment() -> dict[str, str]:
    env = read_dotenv()
    env.update(os.environ)
    return env


def expand(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, str):
        def sub(m: re.Match[str]) -> str:
            name, default = m.group(1), m.group(2)
            v = env.get(name, "")
            if v:
                return v
            return expand(default, env) if default is not None else ""
        prev = None
        while prev != value and isinstance(value, str) and "${" in value:
            prev, value = value, _VAR.sub(sub, value)
        return value
    if isinstance(value, dict):
        return {k: expand(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v, env) for v in value]
    return value


class ConfigError(RuntimeError):
    pass


class Config:
    """All config files, expanded. Access as `cfg.routing["signals"]` or `cfg["routing"]`."""

    def __init__(self, data: dict[str, dict[str, Any]], root: Path):
        self._data = data
        self.root = root

    def __getattr__(self, name: str) -> dict[str, Any]:
        try:
            return self._data[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __getitem__(self, name: str) -> dict[str, Any]:
        return self._data[name]

    def sha256(self, *names: str) -> str:
        blob = json.dumps({n: self._data[n] for n in names}, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    # Convenience accessors used across modules
    def substantive(self, category: str, question_challenge: bool = False) -> bool:
        c = self.taxonomy["categories"].get(category, {})
        sub = c.get("substantive", True)
        if sub == "extractor_decides":
            return bool(question_challenge)
        return bool(sub)

    def fixable(self, category: str) -> bool:
        return bool(self.taxonomy["categories"].get(category, {}).get("fixable_default", False))

    def severity_weight(self, severity: str) -> float:
        return float(self.taxonomy["severities"].get(severity, {}).get("weight", 1))

    def model_display(self, model_id: str | None) -> str:
        if not model_id:
            return ""
        names = self.models.get("display_names", {})
        if model_id in names:
            return str(names[model_id])
        for role in self.models["roles"].values():
            if role.get("model") == model_id and role.get("display"):
                return str(role["display"])
        return model_id


def load_config(config_dir: Path | None = None, *, validate: bool = True) -> Config:
    s = get_settings()
    cdir = config_dir or s.config_dir
    env = environment()
    data: dict[str, dict[str, Any]] = {}
    for name in CONFIG_FILES:
        f = cdir / f"{name}.yaml"
        if not f.exists():
            raise ConfigError(f"Missing config file: {f}")
        try:
            raw = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"{f.name}: invalid YAML: {e}") from e
        data[name] = expand(raw, env)
    cfg = Config(data, cdir)
    if validate:
        errors = validate_config(cfg)
        if errors:
            raise ConfigError("Invalid configuration:\n  " + "\n  ".join(errors))
    return cfg


def validate_config(cfg: Config) -> list[str]:
    """JSON Schema validation per file, plus cross-file rules. Returns error strings ("file: key: message")."""
    import jsonschema

    errors: list[str] = []
    sdir = cfg.root / "schemas" / "config"
    for name in CONFIG_FILES:
        sf = sdir / f"{name}.schema.json"
        if not sf.exists():
            errors.append(f"{name}.yaml: schema file missing ({sf.name})")
            continue
        schema = json.loads(sf.read_text())
        v = jsonschema.Draft202012Validator(schema)
        for err in sorted(v.iter_errors(cfg[name]), key=lambda e: list(e.path)):
            key = ".".join(str(p) for p in err.path) or "(root)"
            errors.append(f"{name}.yaml: {key}: {err.message}")
    cats = set(cfg.taxonomy.get("categories", {}))
    for sig, spec in cfg.routing.get("signals", {}).items():
        for c in spec.get("covering_categories", []) or []:
            if c not in cats:
                errors.append(f"routing.yaml: signals.{sig}.covering_categories: unknown category {c!r}")
    for kind, lst in cfg.taxonomy.get("outcome_compat", {}).items():
        for c in lst:
            if c not in cats:
                errors.append(f"taxonomy.yaml: outcome_compat.{kind}: unknown category {c!r}")
    return errors


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()


def reset_config() -> None:
    get_config.cache_clear()

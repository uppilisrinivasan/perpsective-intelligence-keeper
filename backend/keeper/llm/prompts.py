"""Prompt files: YAML front matter + a Jinja2 body split by `{# system #}` / `{# user #}` (methodology 15 §1).

Untrusted values are rendered only through the `untrusted` filter, which redacts them and wraps them in a data
block with a per-install boundary that the content cannot predict.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2
import yaml

from keeper.config import get_config, get_settings
from keeper.llm.redact import Redactor

_SYS, _USER = "{# system #}", "{# user #}"


@dataclass
class Prompt:
    id: str
    version: int
    role: str
    temperature: float
    top_p: float
    reasoning: str
    max_output_tokens: int
    output_schema: str | None
    allow_fallback: bool
    cache: bool
    seed: int | None
    trim: list[str]
    system_src: str
    user_src: str
    sha256: str
    meta: dict[str, Any] = field(default_factory=dict)


def prompts_dir() -> Path:
    return get_settings().config_dir / "prompts"


def _split(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("prompt file must start with front matter")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.lstrip("\n")


def prompt_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=64)
def load_prompt(prompt_id: str) -> Prompt:
    path = prompts_dir() / f"{prompt_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt {prompt_id} not found at {path}")
    meta, body = _split(path.read_text(encoding="utf-8"))
    if _SYS not in body or _USER not in body:
        raise ValueError(f"prompt {prompt_id}: needs {_SYS} and {_USER} sections")
    sys_part, user_part = body.split(_USER, 1)
    sys_part = sys_part.split(_SYS, 1)[1]
    return Prompt(
        id=meta["id"], version=int(meta["version"]), role=meta["role"], temperature=float(meta.get("temperature", 0)),
        top_p=float(meta.get("top_p", 1)), reasoning=str(meta.get("reasoning", "off")),
        max_output_tokens=int(meta.get("max_output_tokens", 1500)), output_schema=meta.get("output_schema"),
        allow_fallback=bool(meta.get("allow_fallback", True)), cache=bool(meta.get("cache", True)),
        seed=meta.get("seed"), trim=list(meta.get("trim", []) or []), system_src=sys_part.strip("\n"),
        user_src=user_part.strip("\n"), sha256=prompt_sha(path), meta=meta)


def all_prompt_ids() -> list[str]:
    return sorted(p.stem for p in prompts_dir().glob("*.md") if not p.name.startswith("_"))


def _salt() -> bytes:
    rt = get_settings().runtime_dir
    f = rt / "boundary.salt"
    if not f.exists():
        rt.mkdir(parents=True, exist_ok=True)
        f.write_bytes(os.urandom(16))
    return f.read_bytes()


class Renderer:
    """One render = one Redactor, so replacements are stable across a call's inputs."""

    def __init__(self) -> None:
        self.redactor = Redactor(get_config().redaction)
        self.salt = _salt()
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(prompts_dir())),
                                      undefined=jinja2.StrictUndefined, autoescape=False, keep_trailing_newline=True)
        self.env.filters["untrusted"] = self.untrusted

    def untrusted(self, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        text = self.redactor(text)
        bid = hmac.new(self.salt, text.encode(), hashlib.sha256).hexdigest()[:6]
        text = text.replace("</untrusted", "<\\/untrusted").replace("<untrusted", "<\\untrusted")
        return f'<untrusted id="{bid}">\n{text}\n</untrusted id="{bid}">'

    def render(self, prompt: Prompt, inputs: dict[str, Any]) -> list[dict[str, str]]:
        ctx = {k: v for k, v in inputs.items() if not k.startswith("_")}
        system = self.env.from_string(prompt.system_src).render(**ctx).strip()
        user = self.env.from_string(prompt.user_src).render(**ctx).strip()
        msgs = [{"role": "system", "content": system}]
        if user:
            msgs.append({"role": "user", "content": user})
        return msgs


def render(prompt_id: str, inputs: dict[str, Any]) -> tuple[Prompt, list[dict[str, str]], Redactor]:
    p = load_prompt(prompt_id)
    r = Renderer()
    return p, r.render(p, inputs), r.redactor


def lock_entries() -> list[dict[str, Any]]:
    out = []
    for pid in all_prompt_ids():
        p = load_prompt(pid)
        out.append({"id": p.id, "version": p.version, "sha256": p.sha256})
    return out


def write_lock() -> Path:
    path = prompts_dir() / "versions.lock"
    path.write_text(json.dumps(lock_entries(), indent=2) + "\n")
    return path


def check_lock() -> list[str]:
    """Problems where a prompt changed without a version bump (or the lock is stale)."""
    path = prompts_dir() / "versions.lock"
    if not path.exists():
        return ["config/prompts/versions.lock is missing"]
    locked = {e["id"]: e for e in json.loads(path.read_text())}
    problems = []
    for e in lock_entries():
        old = locked.get(e["id"])
        if old is None:
            problems.append(f"{e['id']}: not in versions.lock")
        elif old["sha256"] != e["sha256"] and old["version"] == e["version"]:
            problems.append(f"{e['id']}: changed without a version bump (v{e['version']})")
        elif old["sha256"] != e["sha256"]:
            problems.append(f"{e['id']}: versions.lock is stale (run python -m keeper.cli prompts-lock)")
    return problems

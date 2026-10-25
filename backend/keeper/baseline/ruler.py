"""The ruler: the exact, pinned configuration of the generic review (methodology 03 §3). Its ID is the content
hash, so any change to the model, prompt, parameters, tools, context bounds or taxonomy is a new ruler."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.db import models as M
from keeper.llm.prompts import load_prompt
from keeper.sandbox import tools


@lru_cache(maxsize=1)
def tool_versions() -> dict[str, str]:
    return {"ruff": tools.version("ruff"), "bandit": tools.version("bandit")}


def spec(model_id: str) -> dict[str, Any]:
    cfg = get_config()
    b = cfg.baseline
    p = load_prompt(b["llm"]["prompt"])
    return {"llm": {"model_id": model_id, "prompt_id": p.id, "prompt_version": p.version, "prompt_sha256": p.sha256,
                    "params": {k: b["llm"][k] for k in ("temperature", "top_p", "seed", "reasoning")}},
            "tools": {**tool_versions(), "ruff_select": b["tools"]["ruff"]["select"],
                      "enabled": {k: v["enabled"] for k, v in b["tools"].items()}},
            "context_config_sha256": cfg.sha256("context"), "taxonomy_sha256": cfg.sha256("taxonomy")}


def ruler_id(s: dict[str, Any]) -> str:
    return "rul_" + hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()[:16]


def ensure(db: Session, model_id: str) -> M.Ruler:
    s = spec(model_id)
    rid = ruler_id(s)
    row = db.get(M.Ruler, rid)
    if row is None:
        row = M.Ruler(id=rid, spec=s)
        db.add(row)
        db.flush()
    return row

"""Response cache keyed by request hash (NFR-COST-2)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from keeper.db.models import LLMCacheRow
from keeper.db.session import session_scope


def request_hash(model_id: str, prompt_sha: str, messages: list[dict[str, Any]], params: dict[str, Any]) -> str:
    blob = json.dumps({"m": model_id, "p": prompt_sha, "msgs": messages, "params": params}, sort_keys=True,
                      default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


_mem: dict[str, dict[str, Any]] = {}


def get(h: str) -> dict[str, Any] | None:
    if h in _mem:
        return _mem[h]
    with session_scope() as db:
        row = db.get(LLMCacheRow, h)
        return dict(row.response) if row else None


def put(h: str, model_id: str, response: dict[str, Any]) -> None:
    from keeper.db import sidecar
    _mem[h] = response
    if len(_mem) > 5000:
        _mem.clear()
    sidecar.add(LLMCacheRow(request_hash=h, model_id=model_id, response=response))

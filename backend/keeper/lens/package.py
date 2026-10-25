"""Lens export and import (methodology 13 §5): a skill package other agents can run, owned by the person."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import jsonschema

from keeper.config import get_settings

SCHEMA_PATH = "schemas/lens_package.schema.json"


def schema() -> dict[str, Any]:
    return json.loads((get_settings().config_dir / SCHEMA_PATH).read_text())


def build(person_login: str, version: dict[str, Any], items: list[dict[str, Any]], card_md: str,
          exemplars: list[dict[str, Any]] | None, licence: str, provenance: dict[str, Any], *,
          include_bias: bool = False) -> bytes:
    lens_json = {"format": "keeper-lens/1", "person": person_login, "version": version,
                 "items": [{k: v for k, v in it.items() if include_bias or k != "bias"} for it in items
                           if include_bias or it.get("status") != "bias_suspected"]}
    jsonschema.validate(lens_json, schema())
    skill = f"""---
name: review-like-{person_login}
description: Review a pull request with {person_login}'s lens — what they notice in code review that a generic
  reviewer misses, learned from their own past reviews.
---

# Reviewing with {person_login}'s lens

1. Read `lens.json`. Each item is something {person_login} notices, with triggers (path globs and code patterns)
   and a statement of what to check.
2. For the pull request, find the items whose triggers match the changed files and added lines.
3. Only raise an item's concern if the change actually has the issue; an item being relevant is not enough.
4. For each concern, cite the item id and explain how this change is like the item's past cases.
5. Also do a normal careful review; the lens adds attention, it never removes it.

Label your output as a lens suggestion. Never post as {person_login}, and never merge, close or approve.
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("lens.json", json.dumps(lens_json, indent=2))
        z.writestr("LENS.md", card_md)
        z.writestr("SKILL.md", skill)
        z.writestr("LICENSE.txt", licence + "\n")
        z.writestr("PROVENANCE.json", json.dumps(provenance, indent=2, default=str))
        if exemplars:
            z.writestr("exemplars.jsonl", "".join(json.dumps(e) + "\n" for e in exemplars))
    return buf.getvalue()


def read(data: bytes) -> dict[str, Any]:
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("the package is larger than 5 MB")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        if "lens.json" not in names:
            raise ValueError("lens.json is missing")
        lens_json = json.loads(z.read("lens.json"))
        jsonschema.validate(lens_json, schema())
        card = z.read("LENS.md").decode() if "LENS.md" in names else ""
    return {"lens": lens_json, "card_md": card}

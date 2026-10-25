"""The lens card (LENS.md): the `lens_card` prompt writes the words from the items; code renders markdown and
checks that every bullet cites real item IDs."""

from __future__ import annotations

import re
from typing import Any

from keeper.core.types import LensItem


async def generate(items: list[LensItem], person: Any, *, gateway: Any, job: Any = None,
                   include_bias: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = [{"id": i.id, "type": i.type, "status": i.status, "category": i.category, "title": i.title,
             "statement": i.statement, "support": i.stats.get("support", 0)} for i in items]
    res = await gateway.call("lens_card", {"person": {"display_name": person.display_name or person.login},
                                           "items": rows, "include_bias": include_bias, "_sim": {"items": rows}},
                             job_id=job.id if job else None, feature="lens")
    ids = {i.id for i in items}
    data = res.data
    for sec in data.get("sections", []):
        sec["bullets"] = [b for b in sec.get("bullets", []) if set(b.get("item_ids", [])) & ids]
    data["sections"] = [s for s in data.get("sections", []) if s["bullets"]]
    return data, {"models": [res.model_id], "llm_call_id": res.call_id}


def render(card: dict[str, Any], person: Any, *, owner_view: bool = True, include_bias: bool = True) -> str:
    name = person.display_name or person.login
    out = [f"# {name}'s lens", "", card.get("summary", "").strip(), ""]
    for sec in card.get("sections", []):
        if not include_bias and "bias" in sec["heading"].lower():
            continue
        out.append(f"## {sec['heading']}")
        out.append("")
        for b in sec["bullets"]:
            cites = " ".join(f"[[lens_item:{i}]]" for i in b.get("item_ids", []))
            out.append(f"- {b['text']} {cites}".rstrip())
        out.append("")
    return "\n".join(out).strip() + "\n"


def plain(card_md: str) -> str:
    """The card without citation markers (for LENS.md in an exported package)."""
    return re.sub(r" ?\[\[lens_item:[^\]\s]+\]\]", "", card_md)


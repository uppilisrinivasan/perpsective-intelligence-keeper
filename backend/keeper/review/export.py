"""Exports of a review draft for the user to post themselves (FR-REV-4/5). Every export carries the label line."""

from __future__ import annotations

import json
from typing import Any


def with_label(body: str, label: str) -> str:
    body = (body or "").rstrip()
    return body if body.endswith(label) else f"{body}\n\n{label}"


def markdown(draft: dict[str, Any], label: str, header: str) -> str:
    out = [f"<!-- {header} -->", draft["body_md"].strip()]
    for c in draft.get("comments", []):
        out.append(f"\n**{c['path']}:{c['line']}**\n\n{c['body_md']}")
    return with_label("\n".join(out), label) + "\n"


def github_json(draft: dict[str, Any], label: str) -> str:
    """The exact body of GitHub's "create a review" API (POST /repos/{o}/{r}/pulls/{n}/reviews)."""
    payload = {"body": with_label(draft["body_md"], label), "event": draft.get("event", "COMMENT"),
               "comments": [{"path": c["path"], "line": c["line"], "side": c.get("side", "RIGHT"),
                             "body": with_label(c["body_md"], label)} for c in draft.get("comments", [])]}
    return json.dumps(payload, indent=2)


def gh_command(owner: str, repo: str, number: int) -> str:
    return (f"gh api repos/{owner}/{repo}/pulls/{number}/reviews --method POST --input review.json"
            "   # run it yourself; Keeper never posts")

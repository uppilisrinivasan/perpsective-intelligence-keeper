"""A8: the review draft (methodology 06/07; FR-REV-3). Composed from routed findings the maintainer would raise,
grouped by severity, in their format habits, always labelled as Keeper's. Keeper never posts it."""

from __future__ import annotations

from typing import Any

from keeper.config import get_config


def draft_findings(routed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Accepted and edited findings when there is feedback; otherwise the suggested ones (edge, blind spot after a
    good catch, shared), never dismissed ones and never 'other model notes'."""
    decided = [r for r in routed if r["user_state"] in ("accepted", "edited", "good_catch")]
    if decided:
        return decided
    return [r for r in routed if r["user_state"] != "dismissed" and r["lane"] in ("edge", "shared", "blind_spot")]


def event_for(findings: list[dict[str, Any]]) -> str:
    rules = get_config().review["draft_event_rules"]
    return rules["blocker_or_major"] if any((f.get("user_severity") or f["severity"]) in ("blocker", "major")
                                            for f in findings) else rules["otherwise"]


async def compose(person: Any, version: int | None, summary: str, findings: list[dict[str, Any]],
                  style: dict[str, Any], *, gateway: Any, job_id: str | None = None, slop_reply: bool = False,
                  slop_evidence: list[str] | None = None) -> dict[str, Any]:
    cfg = get_config().review
    name = person.display_name or person.login
    label = cfg["label_line"].format(maintainer=name)
    if slop_reply:
        res = await gateway.call("slop_reply", {"summary": summary, "evidence": slop_evidence or [],
                                                "template": cfg["slop_reply_template"],
                                                "_sim": {"template": cfg["slop_reply_template"]}},
                                 job_id=job_id, feature="queue")
        return {"body_md": res.data["body_md"], "comments": [], "event": "COMMENT", "model": res.meta(),
                "label": label}
    rows = [{"id": f["finding_id"], "severity": f.get("user_severity") or f["severity"], "category": f["category"],
             "path": f["anchor"].get("path"), "line": f["anchor"].get("start_line"),
             "statement": f.get("user_text") or f["statement"], "suggestion": f.get("suggestion"),
             "citations": [f"#{n}" for n in f.get("cited_prs", [])][:3]} for f in findings]
    hints = ", ".join(f"{k}={v}" for k, v in (style or {}).items()) or "none known"
    res = await gateway.call("review_draft", {"person": {"display_name": name}, "findings": rows, "style_hints": hints,
                                              "summary": summary, "_sim": {"findings": rows, "style": style,
                                                                           "event": event_for(findings)}},
                             job_id=job_id, feature="pr")
    d = res.data
    valid = {(r["path"], r["line"]) for r in rows if r["path"] and r["line"]}
    comments = [c for c in d.get("comments", []) if (c["path"], c["line"]) in valid]
    return {"body_md": d["body_md"], "comments": comments, "event": d.get("event") or event_for(findings),
            "model": res.meta(), "label": label}

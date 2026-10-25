"""C(S): the pinned generic review plus static tools on changed lines (methodology 03). The stored reading for a
(head SHA, ruler) *is* C(S) for every later comparison, so it is computed once and reused."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.core.errors import ModelUnavailable
from keeper.core.types import Anchor, Finding, PRContext
from keeper.db import models as M
from keeper.db import repo as R
from keeper.findings.anchors import snap
from keeper.findings.merge import merge_duplicates
from keeper.ids import stable_id
from keeper.sandbox import tools
from keeper.sources import git as G


def static_findings(project: M.Project, ctx: PRContext, ruler_id: str) -> list[Finding]:
    cfg = get_config().baseline
    changed = [f.path for f in ctx.files if f.path.endswith(".py") and not f.binary and f.status != "removed"]
    if not changed or not project.repo_path:
        return []
    texts = {p: t for p, t in G.read_many(project.repo_path, ctx.head_sha, changed + ["pyproject.toml"]).items() if t}
    hits = tools.run_static(texts, ruff_select=cfg["tools"]["ruff"]["select"],
                            ruff=cfg["tools"]["ruff"]["enabled"], bandit=cfg["tools"]["bandit"]["enabled"])
    added = {p: {ln for ln, _ in ctx.added_lines.get(p, [])} for p in changed}
    out: list[Finding] = []
    cmap = cfg["tools"]["ruff"]["category_map"]
    err_prefixes = tuple(cfg.get("ruff_error_prefixes", ["F", "B"]))
    for h in hits["ruff"]:
        if h["line"] not in added.get(h["path"], set()):
            continue
        prefix = next((k for k in cmap if k != "default" and h["code"].startswith(k)), None)
        cat = cmap.get(prefix, cmap["default"]) if prefix else cmap["default"]
        sev = cfg["severity_map"]["ruff"]["error" if h["code"].startswith(err_prefixes) else "warning"]
        out.append(Finding(id=stable_id("fnd", ctx.repo, ctx.number, ctx.head_sha, ruler_id, "ruff", h["path"],
                                        h["line"], h["code"]), project_id=project.id, pr_number=ctx.number,
                           head_sha=ctx.head_sha, source="baseline",
                           anchor=Anchor(scope="line", path=h["path"], start_line=h["line"], end_line=h["line"]),
                           category=cat, severity=sev, kind="tool", statement=f"{h['message']} ({h['code']})",
                           substantive=get_config().substantive(cat), confidence="high",
                           refs={"tool": f"ruff:{h['code']}"}))
    for h in hits["bandit"]:
        if h["line"] not in added.get(h["path"], set()):
            continue
        sev = cfg["severity_map"]["bandit"].get(h["severity"], "nit")
        out.append(Finding(id=stable_id("fnd", ctx.repo, ctx.number, ctx.head_sha, ruler_id, "bandit", h["path"],
                                        h["line"], h["code"]), project_id=project.id, pr_number=ctx.number,
                           head_sha=ctx.head_sha, source="baseline",
                           anchor=Anchor(scope="line", path=h["path"], start_line=h["line"], end_line=h["line"]),
                           category=cfg["tools"]["bandit"]["category_map"]["default"], severity=sev, kind="tool",
                           statement=f"{h['message']} (bandit {h['code']})", substantive=True, confidence="medium",
                           refs={"tool": f"bandit:{h['code']}"}))
    return out


def taxonomy_list() -> list[dict[str, str]]:
    return [{"id": k, "description": v["description"]} for k, v in get_config().taxonomy["categories"].items()]


def cached(db: Session, project: M.Project, pr_number: int, head_sha: str, ruler_id: str) -> list[Finding] | None:
    rows = db.execute(select(M.FindingRow).where(M.FindingRow.project_id == project.id,
                                                 M.FindingRow.pr_number == pr_number, M.FindingRow.source == "baseline",
                                                 M.FindingRow.head_sha == head_sha, M.FindingRow.ruler_id == ruler_id)
                      ).scalars().all()
    marker = R.get_state(db, f"baseline:{project.id}:{pr_number}:{head_sha}:{ruler_id}")
    if not rows and not marker:
        return None
    return [R.from_row(r) for r in rows]


async def baseline_review(db: Session, project: M.Project, ctx: PRContext, block: str, ruler: M.Ruler, *,
                          gateway: Any, job_id: str | None = None, context: str = "analysis",
                          origin: str = "live") -> tuple[list[Finding], dict[str, Any]]:
    """Return C(S) for this head under this ruler: the stored reading if there is one, else compute and store."""
    hit = cached(db, project, ctx.number, ctx.head_sha, ruler.id)
    if hit is not None:
        return hit, {"cached": True}
    cfg = get_config()
    b = cfg.baseline["llm"]
    # the ruler names its model: if the gateway would fall back, fail instead (G6, test_baseline_never_falls_back)
    if not gateway.fake and gateway.model_for(b["role"]) != ruler.spec["llm"]["model_id"]:
        raise ModelUnavailable("Generic review unavailable: the pinned model differs from this ruler.")
    res = await gateway.call(b["prompt"], {"context_block": block, "taxonomy": taxonomy_list(),
                                           "max_findings": b["max_findings"],
                                           "_sim": {"ctx": ctx.model_dump(mode="json")}},
                             job_id=job_id, feature="analysis")
    if res.model_id != ruler.spec["llm"]["model_id"]:
        raise ModelUnavailable("Generic review unavailable: the gateway answered with a different model.")
    snap_lines = int(cfg.context["anchor_snap_lines"])
    found: list[Finding] = []
    for k, d in enumerate(res.data.get("findings", [])[: int(b["max_findings"])]):
        cat = d["category"] if d["category"] in cfg.taxonomy["categories"] else "correctness"
        anchor = snap(ctx, d.get("path"), d.get("start_line"), d.get("end_line"), snap_lines) \
            if d.get("scope") != "pr" else Anchor(scope="pr")
        sev = d.get("severity", "minor")
        found.append(Finding(id=stable_id("fnd", project.id, ctx.number, ctx.head_sha, ruler.id, "llm", k),
                             project_id=project.id, pr_number=ctx.number, head_sha=ctx.head_sha, source="baseline",
                             anchor=anchor, category=cat, severity=sev,
                             kind="change_request" if sev in ("blocker", "major") else "comment",
                             statement=d["statement"].strip(), rationale=d.get("rationale"),
                             suggestion=d.get("suggestion"), substantive=cfg.substantive(cat),
                             confidence=d.get("certainty", "medium"), refs={}, llm_call_id=res.call_id))
    found += static_findings(project, ctx, ruler.id)
    found = merge_duplicates(found, cfg.context["merge_duplicates"])
    db.execute(delete(M.FindingRow).where(M.FindingRow.project_id == project.id,
                                          M.FindingRow.pr_number == ctx.number, M.FindingRow.source == "baseline",
                                          M.FindingRow.head_sha == ctx.head_sha, M.FindingRow.ruler_id == ruler.id))
    for f in found:
        db.add(R.to_row(f, origin=origin, context=context, ruler_id=ruler.id))
    R.set_state(db, f"baseline:{project.id}:{ctx.number}:{ctx.head_sha}:{ruler.id}", {"n": len(found)})
    db.flush()
    return found, {"cached": False, "model": res.meta()}

"""The analysis pipeline, A1–A10 (methodology README §2.2), idempotent per (head SHA, ruler, lens version)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.analysis import codeindex
from keeper.analysis.context import build_context, hunk_excerpt
from keeper.baseline.review import baseline_review
from keeper.config import get_config
from keeper.core.errors import ModelUnavailable
from keeper.core.globs import area_of, match
from keeper.core.types import Finding, LensItem, Matching, RiskSignal
from keeper.db import models as M
from keeper.db import repo as R
from keeper.ids import stable_id
from keeper.lens.apply import apply_lens, load_items
from keeper.residual.match import match as match_findings
from keeper.review import draft as D
from keeper.route import attention as ATT
from keeper.route import handoff as HO
from keeper.route import lanes as LANES
from keeper.route import risk as RISK
from keeper.route import triage as TRI
from keeper.sources import git as G
from keeper.sources import osv, tavily


def current_version(db: Session, lens: M.Lens) -> M.LensVersion | None:
    return db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id, M.LensVersion.status == "ready")
                      .order_by(M.LensVersion.version.desc())).scalars().first()


def project_lenses(db: Session, project: M.Project) -> list[tuple[M.Lens, M.LensVersion, M.Person]]:
    out = []
    for lens in db.execute(select(M.Lens).where(M.Lens.project_id == project.id, M.Lens.status == "active")).scalars():
        v = current_version(db, lens)
        p = db.get(M.Person, lens.person_id)
        if v and p:
            out.append((lens, v, p))
    return out


def blind_spot_matches(baseline: list[Finding], lb: Matching, items: list[LensItem]) -> dict[str, str]:
    """Code first: a baseline-only finding matches a blind-spot item when the item's triggers fire on its file and
    the categories agree (methodology 07 §1)."""
    out: dict[str, str] = {}
    matched_b = {p.b_id for p in lb.pairs}
    bs = [i for i in items if i.type == "blind_spot" and i.status == "validated"]
    for f in baseline:
        if f.id in matched_b or not f.anchor.path:
            continue
        for it in bs:
            if it.category == f.category and any(match(f.anchor.path, g) for g in it.triggers.paths):
                out[f.id] = it.id
                break
    return out


def person_area_counts(db: Session, project: M.Project, person_id: str, before: datetime | None, depth: int
                       ) -> dict[str, int]:
    c: Counter[str] = Counter()
    for f in R.findings(db, project.id, source="human", person_id=person_id, context="history"):
        if f.substantive and f.anchor.path and (before is None or (f.created_at and f.created_at < before)):
            c[area_of(f.anchor.path, depth)] += 1
    return dict(c)


def reasons_for(routed: list[dict[str, Any]], signals: list[RiskSignal], slop: dict[str, Any], name: str,
                items: dict[str, LensItem], lane: str, owners: dict[str, str]) -> list[dict[str, Any]]:
    tpl = get_config().review["reasons"]
    out = []
    for s in signals:
        if s.covered:
            out.append({"kind": "signal", "label": tpl["signal_covered"].format(label=s.label, owner=owners.get(
                s.covered_by[0], name)), "detail": ", ".join(s.paths[:3])})
        else:
            out.append({"kind": "signal", "label": tpl["signal"].format(label=s.label), "detail": ", ".join(s.paths[:3])})
    for r in routed:
        if r["lane"] == "edge":
            cites = [items[i] for i in r["lens_item_ids"] if i in items]
            if cites:
                it = max(cites, key=lambda i: i.stats.get("support", 0))
                out.append({"kind": "edge", "label": tpl["edge_item"].format(name=name, title=it.title.rstrip("."),
                                                                             n=it.stats.get("support", 0)),
                            "detail": r["statement"]})
        elif r["lane"] == "blind_spot" and r.get("blind_spot_item_id") in items:
            it = items[r["blind_spot_item_id"]]
            o = it.stats.get("outcome") or {}
            out.append({"kind": "blind_spot", "label": tpl["blind_spot"].format(
                name=name, k=o.get("bad_when_ignored", 0), n=max(o.get("ignored", 0), o.get("bad_when_ignored", 0))),
                "detail": r["statement"]})
    if slop.get("is_slop"):
        out.append({"kind": "slop", "label": tpl["slop"].format(evidence=(slop["evidence"] or ["generic"])[0]),
                    "detail": "; ".join(slop["evidence"][:3])})
    if lane == "shared":
        has = any(r["lane"] == "shared" for r in routed)
        out.append({"kind": "shared", "label": (tpl["shared"] if has else tpl["nothing"]).format(name=name)})
    seen, uniq = set(), []
    for r in out:
        if r["label"] not in seen:
            seen.add(r["label"])
            uniq.append(r)
    return uniq


async def analyze_pr(db: Session, project: M.Project, pr: M.Pull, *, gateway: Any, ruler: M.Ruler,
                     maintainer: M.Person, lens_version: M.LensVersion | None, lens_paused: bool = False,
                     job: Any = None, purpose: str = "queue", head_sha: str | None = None,
                     exemplars_before: datetime | None = None, origin: str = "live", handoff: bool = True,
                     draft: bool = True) -> M.Analysis:
    cfg = get_config()
    rcfg = cfg.routing
    job_id = job.id if job else None
    ev = (lambda stage: job.event("analysis.step", {"pr_number": pr.number, "stage": stage})) if job else None
    # ---- A1 context and risk signals
    if ev:
        await ev("context")
    ctx, block = build_context(db, project, pr, head_sha=head_sha)
    ctx_na, block_na = build_context(db, project, pr, no_author=True, head_sha=head_sha)
    lenses = project_lenses(db, project)
    covering: list[LensItem] = []
    owners: dict[str, str] = {}
    for _lens, v, p in lenses:
        for it in load_items(db, v.id):
            covering.append(it)
            owners[it.id] = p.display_name or p.login
    py_base = G.show(project.repo_path, pr.base_sha or "HEAD", "pyproject.toml") if project.repo_path else None
    py_head = G.show(project.repo_path, ctx.head_sha, "pyproject.toml") if project.repo_path else None
    areas = person_area_counts(db, project, maintainer.id, ctx.created_at, int(cfg.find["area_depth"]))
    signals = RISK.evaluate(ctx, rcfg, pyproject_base=py_base, pyproject_head=py_head, covering_items=covering,
                            person_area_findings=areas, area_depth=int(cfg.find["area_depth"]))
    # ---- A2 baseline (the ruler); never falls back to another model
    if ev:
        await ev("baseline")
    baseline_unavailable = False
    try:
        baseline, bmeta = await baseline_review(db, project, ctx, block, ruler, gateway=gateway, job_id=job_id,
                                                context="history" if purpose != "queue" else "analysis", origin=origin)
    except ModelUnavailable:
        baseline, bmeta, baseline_unavailable = [], {}, True
    # ---- A3–A4 lens
    lens_findings: list[Finding] = []
    lmeta: dict[str, Any] = {}
    items: dict[str, LensItem] = {}
    if lens_version is not None and not lens_paused:
        if ev:
            await ev("lens_recall")
        lens_findings, lmeta = await apply_lens(db, project, pr, ctx, block, lens_version, maintainer, ruler.id,
                                                gateway=gateway, job_id=job_id, context=purpose,
                                                exemplars_before=exemplars_before, origin=origin)
        items = {i.id: i for i in load_items(db, lens_version.id)}
        if ev:
            await ev("lens_review")
    # ---- A5 match lens vs baseline
    if ev:
        await ev("match")
    lb, _ = await match_findings(lens_findings, baseline, cfg.matching, gateway=gateway, job_id=job_id, feature="analysis",
                        hunk=lambda f: hunk_excerpt(ctx, f.anchor.path, f.anchor.start_line,
                                                    int(cfg.matching.get("judge_hunk_lines", 8))))
    # ---- A6 route
    if ev:
        await ev("route")
    bsm = blind_spot_matches(baseline, lb, list(items.values()))
    routed = LANES.route_findings(lens_findings, baseline, lb, bsm, cfg.taxonomy)
    lane = LANES.pr_lane(routed, signals)
    # ---- A7 triage
    if ev:
        await ev("triage")
    idx = codeindex.build(project.repo_path, ctx.head_sha) if project.repo_path else {}
    known = codeindex.known_symbols(idx)
    pkg = (project.meta or {}).get("package") or project.repo
    tri = await TRI.triage(ctx_na, block_na, codeindex.summary(idx), known, pkg, rcfg, gateway=gateway,
                           job_id=job_id)
    fixed_shared = 0
    edge_cells = db.execute(select(M.EdgeMapCell).where(M.EdgeMapCell.lens_version_id == (
        lens_version.id if lens_version else ""), M.EdgeMapCell.kind == "top")).scalars().all()
    pr_areas = sorted({area_of(f.path, int(cfg.find["area_depth"])) for f in ctx.files})
    from keeper.find.edge_map import attention_bonus
    bonus = attention_bonus([{"area": c.area, "value": c.value} for c in edge_cells], pr_areas, cfg.find) \
        if edge_cells else 0.0
    minutes = ATT.attention_minutes(lane, routed, ctx.changed_lines, rcfg, edge_map_bonus=bonus,
                                    fixed_shared=fixed_shared)
    # ---- persist
    db.execute(delete(M.Analysis).where(M.Analysis.project_id == project.id, M.Analysis.pr_number == pr.number,
                                        M.Analysis.head_sha == ctx.head_sha, M.Analysis.ruler_id == ruler.id,
                                        M.Analysis.lens_version_id == (lens_version.id if lens_version else None),
                                        M.Analysis.origin == origin, M.Analysis.purpose == purpose))
    if lens_version is not None:
        db.execute(delete(M.FindingRow).where(M.FindingRow.project_id == project.id,
                                              M.FindingRow.pr_number == pr.number, M.FindingRow.source == "lens",
                                              M.FindingRow.lens_version_id == lens_version.id,
                                              M.FindingRow.head_sha == ctx.head_sha, M.FindingRow.context == purpose))
    for f in lens_findings:
        db.add(R.to_row(f, origin=origin, context=purpose, lens_version_id=lens_version.id if lens_version else None,
                        ruler_id=ruler.id, title=(f.refs.get("title") or None)))
    aid = stable_id("ana", project.id, pr.number, ctx.head_sha, ruler.id, lens_version.id if lens_version else "",
                    origin, purpose)
    fmap = {f.id: f for f in lens_findings + baseline}
    routed_out = []
    for r in routed:
        f = fmap[r.finding_id]
        cited = []
        for e in f.refs.get("exemplar_finding_ids", []) or []:
            row = db.get(M.FindingRow, e)
            if row:
                cited.append(row.pr_number)
        routed_out.append({**r.model_dump(), "statement": f.statement, "severity": f.severity, "category": f.category,
                           "anchor": f.anchor.model_dump(), "lens_item_ids": f.refs.get("lens_item_ids", []),
                           "cited_prs": sorted(set(cited)), "suggestion": f.suggestion, "user_state": "open",
                           "finding_id": f.id})
    reasons = reasons_for(routed_out, signals, tri["slop"], maintainer.display_name or maintainer.login, items,
                          lane, owners)
    if baseline_unavailable:
        reasons.append({"kind": "warning", "label": cfg.review["reasons"]["baseline_unavailable"].format(
            model=cfg.model_display(ruler.spec["llm"]["model_id"]))})
    models = sorted({m for m in [bmeta.get("model", {}).get("model"), (lmeta.get("model") or {}).get("model"),
                                 (lmeta.get("recall_model") or {}).get("model"), tri["model"]["model"]] if m})
    a = M.Analysis(id=aid, project_id=project.id, pr_number=pr.number, head_sha=ctx.head_sha, ruler_id=ruler.id,
                   lens_version_id=lens_version.id if lens_version else None, purpose=purpose, status="ready",
                   pr_lane=lane, attention_minutes=minutes, summary=tri["summary"], slop_score=tri["slop"]["score"],
                   signals=[s.model_dump() for s in signals], reasons=reasons, recall_mode=lmeta.get("recall_mode"),
                   stats={"slop": tri["slop"], "touches_public_api": tri["touches_public_api"],
                          "description_matches_diff": tri["description_matches_diff"],
                          "dropped_uncited": lmeta.get("dropped_uncited", 0), "fired": lmeta.get("fired", []),
                          "recalled_items": lmeta.get("recalled_items", []), "exemplars": lmeta.get("exemplars", []),
                          "baseline_unavailable": baseline_unavailable, "lens_paused": lens_paused,
                          "changed_lines": ctx.changed_lines, "areas": pr_areas,
                          "model_meta": {"baseline": bmeta.get("model"), "lens": lmeta.get("model"),
                                         "recall": lmeta.get("recall_model"), "triage": tri["model"]}},
                   models=models, job_id=job_id, origin=origin)
    db.add(a)
    db.flush()
    for _k, r in enumerate(routed_out):
        db.add(M.RoutedFindingRow(id=stable_id("rf", aid, r["finding_id"]), analysis_id=aid, finding_id=r["finding_id"],
                                  paired_finding_id=r["paired_finding_id"], lane=r["lane"], action=r["action"],
                                  fixable=r["fixable"], blind_spot_item_id=r["blind_spot_item_id"],
                                  evidence={**r["evidence"], "cited_prs": r["cited_prs"]}))
    for p in lb.judged:
        db.add(M.FindingMatch(id=stable_id("fm", aid, p.a_id, p.b_id), project_id=project.id, pr_number=pr.number,
                              set_a=f"lens:{purpose}", set_b="baseline", a_id=p.a_id, b_id=p.b_id, decision=p.decision,
                              weight=p.weight, assigned=any(q.a_id == p.a_id and q.b_id == p.b_id for q in lb.pairs),
                              rationale=p.rationale, origin=origin))
    db.flush()
    # ---- A8 review draft (or the polite slop reply), A10 hand-off
    if draft and purpose == "queue":
        if ev:
            await ev("draft")
        await make_draft(db, a, maintainer, lens_version, gateway=gateway, job_id=job_id, origin=origin)
    if handoff and purpose == "queue" and lane == "unknown":
        await make_handoff(db, project, pr, a, ctx, signals, maintainer, gateway=gateway, job_id=job_id, origin=origin)
    if job:
        await job.event("analysis.updated", {"pr_number": pr.number, "analysis_id": aid, "lane": lane,
                                             "attention_minutes": minutes})
    return a


def routed_view(db: Session, a: M.Analysis) -> list[dict[str, Any]]:
    rows = db.execute(select(M.RoutedFindingRow).where(M.RoutedFindingRow.analysis_id == a.id)).scalars().all()
    out = []
    for r in rows:
        f = db.get(M.FindingRow, r.finding_id)
        if f is None:
            continue
        out.append({"id": r.id, "finding_id": f.id, "lane": r.lane, "severity": f.severity, "category": f.category,
                    "statement": f.statement, "suggestion": f.suggestion, "user_state": r.user_state,
                    "user_text": r.user_text, "user_severity": r.user_severity,
                    "anchor": {"path": f.path, "start_line": f.start_line}, "cited_prs": r.evidence.get("cited_prs", [])})
    return out


async def make_draft(db: Session, a: M.Analysis, maintainer: M.Person, lv: M.LensVersion | None, *, gateway: Any,
                     job_id: str | None = None, origin: str = "live") -> M.ReviewDraft:
    routed = routed_view(db, a)
    slop = (a.stats or {}).get("slop", {})
    only_shared = all(r["lane"] in ("shared", "baseline_only") for r in routed)
    style = lv.style_hints if lv else {}
    if slop.get("is_slop") and only_shared:
        d = await D.compose(maintainer, lv.version if lv else None, a.summary or "", [], style, gateway=gateway,
                            job_id=job_id, slop_reply=True, slop_evidence=slop.get("evidence", []))
    else:
        fs = D.draft_findings(routed)
        d = await D.compose(maintainer, lv.version if lv else None, a.summary or "", fs, style, gateway=gateway,
                            job_id=job_id)
    db.execute(delete(M.ReviewDraft).where(M.ReviewDraft.analysis_id == a.id))
    row = M.ReviewDraft(id=stable_id("rd", a.id), analysis_id=a.id, body_md=d["body_md"], comments=d["comments"],
                        event=d["event"], edited_by_user=False, models=[d["model"]["model"]], origin=origin)
    db.add(row)
    db.flush()
    return row


async def make_handoff(db: Session, project: M.Project, pr: M.Pull, a: M.Analysis, ctx: Any,
                       signals: list[RiskSignal], maintainer: M.Person, *, gateway: Any, job_id: str | None = None,
                       origin: str = "live") -> M.Handoff:
    cfg = get_config()
    rcfg = cfg.routing
    files = [f.path for f in ctx.files]
    # the pool: people with a consenting lens, CODEOWNERS owners of the changed paths, reviewers of these paths
    from keeper.sources import repo_files
    rules = repo_files.parse_codeowners((G.show(project.repo_path, "HEAD", ".github/CODEOWNERS") or
                                         G.show(project.repo_path, "HEAD", "CODEOWNERS")) if project.repo_path else "")
    owners_login = {o for p in files for o in repo_files.codeowners_for(rules, p)}
    people = {p.id: p for p in db.execute(select(M.Person).where(M.Person.project_id == project.id)).scalars()}
    by_login = {p.login: p for p in people.values()}
    lenses = {p.id: (lens, v) for lens, v, p in project_lenses(db, project)}
    findings = [f for f in R.findings(db, project.id, source="human", context="history") if f.substantive]
    path_counts: Counter[str] = Counter()
    cats: dict[str, Counter[str]] = {}
    for f in findings:
        cats.setdefault(f.person_id or "", Counter())[f.category] += 1
        if f.anchor.path and any(area_of(f.anchor.path, 2) == area_of(p, 2) for p in files):
            path_counts[f.person_id or ""] += 1
    pool_ids = set(lenses) | {by_login[o].id for o in owners_login if o in by_login} | \
        {pid for pid, n in path_counts.items() if n >= int(rcfg["handoff"]["min_path_findings"])}
    pool_ids -= {maintainer.id, pr.author_id}
    pool = []
    for pid in pool_ids:
        p = people.get(pid)
        if p is None or p.role == "bot":
            continue
        pool.append({"person": p, "items": load_items(db, lenses[pid][1].id) if pid in lenses else [],
                     "codeowner": p.login in owners_login, "path_findings": path_counts.get(pid, 0),
                     "cats": dict(cats.get(pid, {}))})
    ranked = HO.rank_candidates(signals, files, pool, dict(cats.get(maintainer.id, {})), rcfg["signals"], rcfg)
    target = ranked[0]["person"] if ranked else None
    # dependency checks: OSV always, Tavily when configured
    py_base = G.show(project.repo_path, pr.base_sha or "HEAD", "pyproject.toml") if project.repo_path else None
    py_head = G.show(project.repo_path, ctx.head_sha, "pyproject.toml") if project.repo_path else None
    deps = RISK.new_dependencies(py_base, py_head, ctx, rcfg.get("dependency_files", []))
    osv_res = [await osv.query(d["name"], d["version"]) for d in deps[:5]]
    tav = {"status": "not_needed", "results": []}
    if deps:
        tav = await tavily.search(f"{deps[0]['name']} PyPI package security advisory maintainer")
    note = {"note_md": "", "checklist": []}
    meta = None
    if target is not None:
        items = [it for it in (ranked[0] and pool[[c["person"].id for c in pool].index(target.id)]["items"])
                 if it.type == "edge" and it.status == "validated"][:5]
        osv_summary = "; ".join(f"{o['name']} {o['version'] or ''}: " + (", ".join(v["id"] for v in o["vulns"]) or
                                                                         "no known vulnerabilities")
                                if not o.get("error") else o["error"] for o in osv_res) or "no new dependencies"
        tav_summary = "; ".join(f"{r['title']} ({r['url']})" for r in tav.get("results", [])[:3]) or \
            ("Web check not configured" if tav.get("status") == "not_configured" else "nothing relevant found")
        res = await gateway.call("handoff_note", {
            "target": {"display_name": target.display_name or target.login, "login": target.login},
            "maintainer": maintainer.display_name or maintainer.login, "pr_number": pr.number,
            "summary": a.summary or pr.title, "signals": [s.model_dump() for s in signals if not s.covered] or
            [s.model_dump() for s in signals], "osv_summary": osv_summary, "tavily_summary": tav_summary,
            "items": [{"title": i.title} for i in items],
            "_sim": {"signals": [s.model_dump() for s in signals], "osv": osv_res, "tavily": tav,
                     "target": target.display_name or target.login, "maintainer": maintainer.display_name or
                     maintainer.login, "pr_number": pr.number, "files": files, "items": [i.title for i in items]}},
            job_id=job_id, feature="pr")
        note, meta = res.data, res.meta()
    db.execute(delete(M.Handoff).where(M.Handoff.analysis_id == a.id))
    row = M.Handoff(id=stable_id("ho", a.id), analysis_id=a.id,
                    candidates=[{"person_id": c["person"].id, "score": c["score"], "competence": c["competence"],
                                 "distance": c["distance"], "why": c["why"]} for c in ranked[:3]],
                    target_person_id=target.id if target else None, note_md=note.get("note_md", ""),
                    checklist=note.get("checklist", []), osv={"packages": osv_res},
                    tavily=tav, models=[meta["model"]] if meta else [], origin=origin)
    db.add(row)
    db.flush()
    return row

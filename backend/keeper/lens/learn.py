"""The learning pipeline L2–L10 for a project (methodology README §2.1), and the edge map (L8)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.analysis.context import build_context, hunk_excerpt
from keeper.baseline.review import baseline_review
from keeper.baseline.ruler import ensure as ensure_ruler
from keeper.config import get_config
from keeper.core.globs import area_of
from keeper.core.timeutil import add_months
from keeper.db import models as M
from keeper.db import repo as R
from keeper.fidelity.run import run_fidelity
from keeper.find import edge_map as EM
from keeper.findings.extract import extract_all, review_material, shallow_reviewers
from keeper.growth.residual import compute as growth_compute
from keeper.ids import stable_id
from keeper.lens.build import build_lens_version
from keeper.lens.governance import active_consent
from keeper.outcomes.link import derive_outcomes, link
from keeper.residual.match import match


async def residual_for(db: Session, project: M.Project, person: M.Person, ruler: M.Ruler, *, gateway: Any,
                       job: Any = None, origin: str = "live") -> dict[str, int]:
    """L3 + L4: for every PR the person reviewed, the baseline at the head they reviewed, then H vs C."""
    cfg = get_config()
    db.execute(delete(M.ResidualSample).where(M.ResidualSample.person_id == person.id,
                                              M.ResidualSample.ruler_id == ruler.id,
                                              M.ResidualSample.evidence == "review"))
    hs_all = R.findings(db, project.id, source="human", person_id=person.id, context="history")
    by_pr: dict[int, list[Any]] = defaultdict(list)
    for f in hs_all:
        by_pr[f.pr_number].append(f)
    pulls = {p.number: p for p in db.execute(select(M.Pull).where(M.Pull.project_id == project.id)).scalars()}
    counts: Counter[str] = Counter()
    for k, (n, hs) in enumerate(sorted(by_pr.items())):
        pr = pulls[n]
        if pr.split == "live":
            continue
        head = hs[0].head_sha or pr.head_sha
        ctx, block = build_context(db, project, pr, head_sha=head)
        base, _ = await baseline_review(db, project, ctx, block, ruler, gateway=gateway, job_id=job.id if job else None,
                                        context="history", origin=origin)
        m, _ = await match(hs, base, cfg.matching, gateway=gateway, job_id=job.id if job else None, feature="lens",
                           hunk=lambda f, ctx=ctx: hunk_excerpt(ctx, f.anchor.path, f.anchor.start_line, 8))
        shallow = person.id in shallow_reviewers(db, pr) and not hs
        w_minus = float(cfg.matching["shallow_review_weight"]) if shallow else 1.0
        at = pr.created_at
        for p in m.pairs:
            db.add(M.ResidualSample(id=stable_id("rs", person.id, ruler.id, p.b_id, p.a_id), project_id=project.id,
                                    finding_id=p.a_id, person_id=person.id, ruler_id=ruler.id, pr_number=n,
                                    klass="shared", matched_finding_id=p.b_id, weight=p.weight, at=at, origin=origin))
            counts["shared"] += 1
        for fid in m.r_plus:
            db.add(M.ResidualSample(id=stable_id("rs", person.id, ruler.id, fid), project_id=project.id, finding_id=fid,
                                    person_id=person.id, ruler_id=ruler.id, pr_number=n, klass="r_plus", weight=1.0,
                                    at=at, origin=origin))
            counts["r_plus"] += 1
        for fid in m.r_minus:
            db.add(M.ResidualSample(id=stable_id("rs", person.id, ruler.id, "minus", fid), project_id=project.id,
                                    finding_id=fid, person_id=person.id, ruler_id=ruler.id, pr_number=n,
                                    klass="r_minus", weight=w_minus, at=at, origin=origin))
            counts["r_minus"] += 1
        for p in m.judged:
            db.add(M.FindingMatch(id=stable_id("fm", "hc", person.id, p.a_id, p.b_id), project_id=project.id,
                                  pr_number=n, set_a=f"human:{person.id}", set_b="baseline", a_id=p.a_id, b_id=p.b_id,
                                  decision=p.decision, weight=p.weight,
                                  assigned=any(q.a_id == p.a_id and q.b_id == p.b_id for q in m.pairs),
                                  rationale=p.rationale, origin=origin))
        if k % 10 == 0:
            db.commit()
            if job is not None:
                await job.progress(k + 1, len(by_pr), stage="residual")
    db.flush()
    return dict(counts)


def edge_map(db: Session, project: M.Project, person: M.Person, lv: M.LensVersion) -> dict[str, Any]:
    """L8: cells (area × category) ranked by residual rate × cost × volume × speed (methodology 10)."""
    cfg = get_config()
    fc = cfg.find
    depth = int(fc["area_depth"])
    pulls = {p.number: p for p in db.execute(select(M.Pull).where(M.Pull.project_id == project.id)).scalars()}
    train = {n for n, p in pulls.items() if p.created_at < lv.cutoff_at and p.split != "live"}
    samples = [s for s in db.execute(select(M.ResidualSample).where(M.ResidualSample.person_id == person.id,
                                                                     M.ResidualSample.ruler_id == lv.ruler_id))
               .scalars() if s.pr_number in train]
    findings = {f.id: f for f in R.findings(db, project.id, context="history")}
    files_by_pr: dict[int, list[str]] = defaultdict(list)
    for pf, n in db.execute(select(M.PullFile.filename, M.Pull.number).join(M.Pull).where(M.Pull.project_id == project.id)):
        files_by_pr[n].append(pf)
    known_areas = sorted({area_of(f, depth) for fs in files_by_pr.values() for f in fs if not f.startswith("tests/")})

    def areas_of(n: int) -> set[str]:
        return {EM.test_area(f, known_areas) if f.startswith("tests/") else area_of(f, depth) for f in files_by_pr[n]}

    reviewed = {s.pr_number for s in samples}
    area_prs: Counter[str] = Counter()
    for n in reviewed:
        area_prs.update(areas_of(n))
    start = add_months(lv.cutoff_at, -int(fc.get("volume_months", 12)))
    vol: Counter[str] = Counter()
    for n in train:
        if pulls[n].created_at >= start:
            vol.update(areas_of(n))
    months = max(1.0, (lv.cutoff_at - max(start, min(p.created_at for p in pulls.values()))).days / 30.44)
    volume = {a: c / months for a, c in vol.items()}
    cells: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"r_plus": 0, "shared": 0, "bad": [], "findings": 0})
    for s in samples:
        f = findings.get(s.finding_id)
        if f is None or not f.substantive:
            continue
        a = (EM.test_area(f.anchor.path, known_areas) if (f.anchor.path or "").startswith("tests/")
             else area_of(f.anchor.path, depth)) if f.anchor.path else next(iter(sorted(areas_of(s.pr_number))), "(root)")
        if s.klass == "r_plus":
            cells[(a, f.category)]["r_plus"] += 1
            cells[(a, f.category)]["findings"] += 1
        elif s.klass == "shared":
            cells[(a, f.category)]["shared"] += 1
            cells[(a, f.category)]["findings"] += 1
    sev = {k: float(v["weight"]) for k, v in cfg.taxonomy["severities"].items()}
    links: dict[str, list[str]] = defaultdict(list)
    for fid, oid in db.execute(select(M.OutcomeLink.finding_id, M.OutcomeLink.outcome_id)):
        links[oid].append(fid)
    for o in db.execute(select(M.Outcome).where(M.Outcome.project_id == project.id,
                                                M.Outcome.kind.in_(["reverted", "post_merge_bug", "follow_up_fix"]))).scalars():
        if o.pr_number not in train:
            continue
        pr = pulls[o.pr_number]
        days = (o.at - pr.merged_at).days if o.at and pr.merged_at else None
        cats = {findings[f].category for f in links.get(o.id, []) if f in findings} or {"correctness"}
        for a in areas_of(o.pr_number):
            for c in cats:
                if (a, c) in cells:
                    cells[(a, c)]["bad"].append({"severity": "major", "days": days, "pr": o.pr_number, "kind": o.kind,
                                                 "issue": (o.evidence or {}).get("issue")})
    tests_present = {a: any(EM.test_area(f, known_areas) == a for fs in files_by_pr.values() for f in fs
                            if f.startswith("tests/")) for a in known_areas}
    computed = EM.compute(dict(cells), dict(area_prs), volume, tests_present, fc, sev)
    anyone: Counter[str] = Counter()
    for f in findings.values():
        if f.source == "human" and f.anchor.path and f.substantive:
            anyone[area_of(f.anchor.path, depth)] += 1
    ranked = EM.rank(computed, fc, {a: anyone.get(a, 0) for a in known_areas})
    db.execute(delete(M.EdgeMapCell).where(M.EdgeMapCell.lens_version_id == lv.id))
    top_keys = {(c["area"], c["category"]) for c in ranked["top"]}
    enough_keys = {(c["area"], c["category"]) for c in ranked["enough"]}
    for c in computed:
        k = (c["area"], c["category"])
        kind = "top" if k in top_keys else ("enough" if k in enough_keys else "cell")
        db.add(M.EdgeMapCell(lens_version_id=lv.id, area=c["area"], category=c["category"], volume=c["volume"],
                             residual_rate=c["residual_rate"], shared_rate=c["shared_rate"], cost=c["cost"],
                             speed_days=c["speed_days"], tests_present=c["tests_present"], value=c["value"], kind=kind,
                             details={"findings": c["findings"], "multiplier": c["multiplier"], "bad": c["bad"][:8]}))
    for g in ranked["gaps"]:
        db.add(M.EdgeMapCell(lens_version_id=lv.id, area=g["area"], category="", volume=g["volume"], residual_rate=0,
                             shared_rate=0, cost=0, value=0, kind="gap", details={"findings": g["findings"]}))
    db.flush()
    return {"cells": len(computed), "top": [(c["area"], c["category"]) for c in ranked["top"]]}


async def learn(db: Session, project: M.Project, *, gateway: Any, job: Any = None, origin: str = "live",
                cutoff_v1: datetime | None = None, people_logins: list[str] | None = None) -> dict[str, Any]:
    """Run L2–L10 for the project's consenting people. Returns a summary."""
    cfg = get_config()
    out: dict[str, Any] = {}
    step = (lambda label, i, n: job.step(label, i, n)) if job else None
    if step:
        await step("Reading what each reviewer noticed", 1, 7)
    out["extract"] = await extract_all(db, project, gateway=gateway, job=job, origin=origin)
    db.commit()
    ruler = ensure_ruler(db, gateway.model_for(cfg.baseline["llm"]["role"]))
    people = db.execute(select(M.Person).where(M.Person.project_id == project.id)).scalars().all()
    consenting = [p for p in people if active_consent(db, project.id, p.id)]
    if people_logins:
        consenting = [p for p in consenting if p.login in people_logins]
    maint = db.get(M.Person, project.primary_maintainer_id) if project.primary_maintainer_id else None
    if step:
        await step("Running the generic review on reviewed PRs", 2, 7)
    for p in consenting:
        out[f"residual:{p.login}"] = await residual_for(db, project, p, ruler, gateway=gateway, job=job, origin=origin)
    if step:
        await step("Linking outcomes to findings", 3, 7)
    out["outcomes"] = derive_outcomes(db, project)
    link(db, project, R.findings(db, project.id, context="history"), int(cfg.matching["line_window"]))
    db.commit()
    demo_now = project.demo_now or datetime.now()
    cut1 = cutoff_v1 or add_months(demo_now, -int(cfg.fidelity["holdout"]["months"]))
    versions: dict[str, Any] = {}
    if step:
        await step("Building the lens", 4, 7)
    if maint is not None and maint in consenting:
        v1 = await build_lens_version(db, project, maint, cutoff=cut1, ruler=ruler, reason="initial_build",
                                      gateway=gateway, job=job, origin=origin)
        versions["v1"] = v1
        out["edge_map_v1"] = edge_map(db, project, maint, v1)
        if step:
            await step("Testing the lens on PRs it never saw", 5, 7)
        fr = await run_fidelity(db, project, maint, v1, ruler, gateway=gateway, job=job, origin=origin)
        versions["fidelity"] = fr
        if step:
            await step("Updating the lens with recent reviews", 6, 7)
        v2 = await build_lens_version(db, project, maint, cutoff=demo_now, ruler=ruler, reason="rebuild_new_reviews",
                                      gateway=gateway, job=job, parent=v1, origin=origin)
        versions["v2"] = v2
        out["edge_map_v2"] = edge_map(db, project, maint, v2)
        lens = db.get(M.Lens, v2.lens_id)
        out["growth"] = growth_compute(db, project, lens, maint, ruler.id, fr, origin=origin)
    for p in consenting:
        if maint is not None and p.id == maint.id:
            continue
        vx = await build_lens_version(db, project, p, cutoff=demo_now, ruler=ruler, reason="initial_build",
                                      gateway=gateway, job=job, origin=origin)
        versions[f"lens:{p.login}"] = vx
    if step:
        await step("Done", 7, 7)
    out["versions"] = {k: getattr(v, "id", None) for k, v in versions.items()}
    out["ruler"] = ruler.id
    return out


_ = (math, timedelta, review_material)

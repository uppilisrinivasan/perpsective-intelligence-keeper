"""A3 and A4: apply a lens version to a PR (methodology 06). Same PR context block and output schema as the
baseline; the only difference is the lens block and the person's past reviews."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.analysis.context import hunk_excerpt
from keeper.calibrate.stats import confidence as item_confidence
from keeper.config import get_config
from keeper.core.textsim import identifiers, tokens
from keeper.core.types import Anchor, Finding, LensItem, PRContext, Triggers
from keeper.db import models as M
from keeper.db import repo as R
from keeper.findings.anchors import snap
from keeper.findings.merge import merge_duplicates
from keeper.ids import stable_id
from keeper.lens.build import counter_present, item_fires

USABLE = ("validated", "candidate")


def load_items(db: Session, lens_version_id: str) -> list[LensItem]:
    out = []
    for r in db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lens_version_id)).scalars():
        ev = db.execute(select(M.LensItemEvidence).where(M.LensItemEvidence.lens_item_id == r.id)).scalars().all()
        out.append(LensItem(id=r.id, lens_version_id=r.lens_version_id, stable_key=r.stable_key, type=r.type,
                            title=r.title, statement=r.statement, rationale=r.rationale or "", category=r.category,
                            severity_typical=r.severity_typical, triggers=Triggers(**(r.triggers or {})),
                            stats=dict(r.stats or {}), status=r.status, owner_override=r.owner_override,
                            member_ids=[e.finding_id for e in ev if e.role == "member" and e.finding_id],
                            exemplar_ids=[e.finding_id for e in ev if e.role == "exemplar" and e.finding_id],
                            counter_example_prs=[e.pr_number for e in ev if e.role == "counter_example" and e.pr_number],
                            provenance=dict(r.provenance or {})))
    return out


def bm25_recall(digest_lines: list[str], ctx: PRContext, k: int) -> list[str]:
    if not digest_lines:
        return []
    corpus = [tokens(ln) for ln in digest_lines]
    bm = BM25Okapi(corpus)
    q = tokens(ctx.title) + [t for f in ctx.files for t in tokens(f.path)]
    for lines in ctx.added_lines.values():
        for _, text in lines[:200]:
            q.extend(x.lower() for x in identifiers(text))
    scores = bm.get_scores(q)
    order = sorted(range(len(digest_lines)), key=lambda i: -scores[i])[:k]
    return [digest_lines[i][1:digest_lines[i].index("]")] for i in order if scores[i] > 0]


def lens_block(person: str, version: int, items: list[LensItem], focus: set[str]) -> str:
    out = [f'<lens owner="{person}" version="v{version}">']
    first = [i for i in items if i.id in focus] + [i for i in items if i.id not in focus and i.status == "validated"
                                                   and i.type == "edge"]
    for it in first:
        if it.type == "blind_spot":
            out.append(f'  <blind_spot id="{it.id}">{it.title}</blind_spot>')
        elif it.id in focus:
            out.append(f'  <item id="{it.id}" type="{it.type}" status="{it.status}" category="{it.category}">\n'
                       f"    <title>{it.title}</title>\n    <statement>{it.statement}</statement>\n"
                       f"    <rationale>{it.rationale}</rationale>\n  </item>")
        else:
            out.append(f'  <item id="{it.id}" brief="true">{it.title}</item>')
    for it in items:
        if it.type == "shared_ground":
            out.append(f'  <routine category="{it.category}">{it.title}</routine>')
    out.append("</lens>")
    return "\n".join(out)


async def apply_lens(db: Session, project: M.Project, pr: M.Pull, ctx: PRContext, block: str,
                     lv: M.LensVersion, person: M.Person, ruler_id: str, *, gateway: Any, job_id: str | None = None,
                     context: str = "analysis", exemplars_before: datetime | None = None, origin: str = "live"
                     ) -> tuple[list[Finding], dict[str, Any]]:
    cfg = get_config()
    lcfg = cfg.lens
    items_all = load_items(db, lv.id)
    review_items = [i for i in items_all if i.type in ("edge", "blind_spot") and i.status in USABLE
                    and i.owner_override != "muted"]
    shared_cats = {i.category for i in items_all if i.type == "shared_ground"}
    files = [f.path for f in ctx.files] + [f.previous_path for f in ctx.files if f.previous_path]
    fired: dict[str, list[tuple[str, int]]] = {}
    for it in review_items:
        ok, where = item_fires(it, files, ctx.added_lines, ctx.removed_lines)
        if ok:
            fired[it.id] = where
    # exemplars and recall never see findings from after this PR was opened (or after the lens cutoff in Proof)
    before = min(x for x in [ctx.created_at, exemplars_before] if x is not None) if (ctx.created_at or
                                                                                    exemplars_before) else None
    own = R.findings(db, project.id, source="human", person_id=person.id, context="history")
    created = {f.id: f.created_at for f in own if f.created_at is not None}
    by_id = {f.id: f for f in own}
    digest_lines = [ln for ln in (lv.digest or "").splitlines()
                    if (fid := ln[1:ln.index("]")] if ln.startswith("[") and "]" in ln else None)
                    and fid in created and (before is None or created[fid] < before)]
    recall_mode = "long_context"
    recalled_items: list[str] = []
    recalled_findings: list[str] = []
    max_items, max_findings = int(lcfg["recall"]["max_items"]), int(lcfg["recall"]["max_findings"])
    try:
        res = await gateway.call("lens_recall", {
            "items": [{"id": i.id, "title": i.title, "statement": i.statement} for i in review_items],
            "digest_lines": digest_lines, "context_block": block, "max_items": max_items, "max_findings": max_findings,
            "_sim": {"ctx": ctx.model_dump(mode="json"), "items": [i.model_dump(mode="json") for i in review_items],
                     "digest_lines": digest_lines, "fired": list(fired)}}, job_id=job_id, feature="analysis")
        valid_items = {i.id for i in review_items}
        recalled_items = [d["item_id"] for d in res.data.get("relevant_items", []) if d["item_id"] in valid_items][:max_items]
        valid_f = {ln[1:ln.index("]")] for ln in digest_lines}
        recalled_findings = [d["finding_id"] for d in res.data.get("relevant_findings", [])
                             if d["finding_id"] in valid_f][:max_findings]
    except Exception:  # noqa: BLE001 — the fast model is optional here; BM25 is the documented fallback
        recall_mode = "bm25"
        recalled_findings = bm25_recall(digest_lines, ctx, max_findings)
        item_of = {fid: it.id for it in review_items for fid in it.member_ids}
        recalled_items = sorted({item_of[f] for f in recalled_findings if f in item_of})
    focus = set(fired) | set(recalled_items)
    ex_ids: list[str] = list(recalled_findings)
    for iid in fired:
        it = next(i for i in review_items if i.id == iid)
        ex_ids += [e for e in it.exemplar_ids if e in created and (before is None or created[e] < before)]
    seen: set[str] = set()
    exemplars = []
    item_of_f = {fid: it.id for it in items_all for fid in it.member_ids}
    for e in ex_ids:
        if e in seen or e not in by_id:
            continue
        seen.add(e)
        f = by_id[e]
        hunk = ""
        rc = None
        if f.refs.get("comment_ids"):
            rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == f.refs["comment_ids"][0])).scalars().first()
        if rc and rc.diff_hunk:
            hunk = "\n".join(rc.diff_hunk.split("\n")[-int(cfg.review["exemplar_hunk_lines"]):])
        exemplars.append({"id": f.id, "pr": f.pr_number, "path": f.anchor.path or "PR",
                          "date": f.created_at.date().isoformat() if f.created_at else "",
                          "item": item_of_f.get(f.id, ""), "hunk": hunk, "said": f.statement})
        if len(exemplars) >= int(cfg.review["max_exemplars"]):
            break
    past = "<past_reviews>\n" + "\n".join(
        f'<exemplar id="{x["id"]}" pr="{x["pr"]}" path="{x["path"]}" date="{x["date"]}" item="{x["item"]}">\n'
        f'<hunk>\n{x["hunk"]}\n</hunk>\n<said>{x["said"]}</said>\n</exemplar>' for x in exemplars) + "\n</past_reviews>"
    lb = lens_block(person.display_name or person.login, lv.version, review_items + [i for i in items_all
                                                                                     if i.type == "shared_ground"], focus)
    res2 = await gateway.call("lens_review", {
        "person": {"display_name": person.display_name or person.login}, "context_block": block,
        "lens_block": lb, "past_reviews_block": past, "max_findings": cfg.baseline["llm"]["max_findings"],
        "taxonomy": [{"id": k, "description": v["description"]} for k, v in cfg.taxonomy["categories"].items()],
        "_sim": {"ctx": ctx.model_dump(mode="json"), "items": [i.model_dump(mode="json") for i in review_items],
                 "fired": {k: v for k, v in fired.items()}, "focus": sorted(focus),
                 "exemplars": [{"id": x["id"], "item": x["item"]} for x in exemplars],
                 "shared_categories": sorted(shared_cats),
                 "counter": {i.id: counter_present(i, ctx.added_lines, files) for i in review_items}}},
        job_id=job_id, feature="analysis")
    valid_items = {i.id: i for i in review_items}
    valid_ex = {x["id"] for x in exemplars}
    snap_lines = int(cfg.context["anchor_snap_lines"])
    out: list[Finding] = []
    dropped = 0
    for k, d in enumerate(res2.data.get("findings", [])):
        cites = [c for c in d.get("lens_item_ids", []) if c in valid_items or (c == "routine" and
                                                                                d.get("category") in shared_cats)]
        if not cites:
            dropped += 1
            continue
        cat = d["category"] if d["category"] in cfg.taxonomy["categories"] else "correctness"
        cited = [valid_items[c] for c in cites if c in valid_items]
        if cited:
            best = max(cited, key=lambda i: (i.status == "validated", i.stats.get("outcome", {}).get("posterior_mean") or 0))
            conf = item_confidence(best.status, (best.stats.get("outcome") or {}).get("posterior_mean"),
                                   d.get("certainty", "medium"), lcfg)
        else:
            conf = "medium" if d.get("certainty") in ("medium", "high") else "low"
        anchor = snap(ctx, d.get("path"), d.get("start_line"), d.get("end_line"), snap_lines) \
            if d.get("scope") != "pr" else Anchor(scope="pr")
        sev = d.get("severity", "minor")
        out.append(Finding(id=stable_id("fnd", project.id, ctx.number, ctx.head_sha, lv.id, ruler_id, context, k),
                           project_id=project.id, pr_number=ctx.number, head_sha=ctx.head_sha, source="lens",
                           person_id=person.id, anchor=anchor, category=cat, severity=sev,
                           kind="change_request" if sev in ("blocker", "major") else "comment",
                           statement=d["statement"].strip(), rationale=d.get("rationale"),
                           suggestion=d.get("suggestion"), substantive=cfg.substantive(cat), confidence=conf,
                           refs={"lens_item_ids": cites, "exemplar_finding_ids": [e for e in d.get(
                               "exemplar_finding_ids", []) if e in valid_ex], "why_similar": d.get("why_similar"),
                               "title": d.get("title")}, llm_call_id=res2.call_id))
    out = merge_duplicates(out, cfg.context["merge_duplicates"])
    return out, {"recall_mode": recall_mode, "fired": sorted(fired), "recalled_items": recalled_items,
                 "exemplars": [x["id"] for x in exemplars], "dropped_uncited": dropped, "model": res2.meta(),
                 "recall_model": res.meta() if recall_mode == "long_context" else None}


def hunk_for_finding(ctx: PRContext, f: Finding, n: int) -> str:
    return hunk_excerpt(ctx, f.anchor.path, f.anchor.start_line, n)


_ = re

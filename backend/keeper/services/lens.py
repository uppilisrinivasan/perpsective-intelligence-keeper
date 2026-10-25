"""The lens (FR-LENS, FR-GOV, FR-FIND): versions, items, diff, actions, export/import, edge map, bias, growth, audit."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from keeper.db import models as M
from keeper.db import repo as R
from keeper.db.session import session_scope
from keeper.ids import new_id, stable_id
from keeper.lens import card as CARD
from keeper.lens import diff as LD
from keeper.lens import governance as GOV
from keeper.lens import package as PKG
from keeper.services import views as V
from keeper.services.common import (
    confirm,
    current_version,
    estimate,
    job_ref,
    name_of,
    person_ref,
    project,
    provenance,
    require_live,
)

OWNER_ROLES = ("maintainer",)


def _lens(db, lid: str) -> M.Lens:  # type: ignore[no-untyped-def]
    lens = db.get(M.Lens, lid)
    if lens is None:
        raise NotFound("Lens not found.")
    return lens


def _owner(ctx: Ctx | None) -> bool:
    return ctx is None or ctx.role in OWNER_ROLES


def _version(db, lens: M.Lens, v: int | None) -> M.LensVersion:  # type: ignore[no-untyped-def]
    if v is None:
        lv = current_version(db, lens)
    else:
        lv = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id, M.LensVersion.version == v)
                        ).scalars().first()
    if lv is None:
        raise NotFound("Lens version not found.")
    return lv


def _health(db, lens: M.Lens) -> str | None:  # type: ignore[no-untyped-def]
    snaps = db.execute(select(M.GrowthSnapshot).where(M.GrowthSnapshot.lens_id == lens.id)
                       .order_by(M.GrowthSnapshot.period_start)).scalars().all()
    live = [s for s in snaps if s.origin == "live"] or snaps
    return live[-1].health_state if live else None


def _counts(db, lv: M.LensVersion) -> dict[str, int]:  # type: ignore[no-untyped-def]
    rows = db.execute(select(M.LensItemRow.type, func.count()).where(M.LensItemRow.lens_version_id == lv.id)
                      .group_by(M.LensItemRow.type)).all()
    return {t: int(c) for t, c in rows}


def list_lenses(pid: str) -> S.LensList:
    with session_scope() as db:
        p = project(db, pid)
        out = []
        for lens in db.execute(select(M.Lens).where(M.Lens.project_id == p.id)).scalars():
            pe = db.get(M.Person, lens.person_id)
            lv = current_version(db, lens)
            out.append(S.LensSummary(id=lens.id, person=person_ref(pe), status=lens.status,
                                     latest_version=lv.version if lv else None, health_state=_health(db, lens),
                                     shared_in_project=lens.shared_in_project))
        out.sort(key=lambda x: (x.person.id != p.primary_maintainer_id, x.person.login))
        return S.LensList(items=out)


def _overview(db, lens: M.Lens) -> S.LensOverview:  # type: ignore[no-untyped-def]
    cfg = get_config()
    pe = db.get(M.Person, lens.person_id)
    p = db.get(M.Project, lens.project_id)
    versions = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id)
                          .order_by(M.LensVersion.version)).scalars().all()
    cur = current_version(db, lens)
    c = db.get(M.Consent, lens.consent_id) if lens.consent_id else None
    unconsumed = 0
    if cur is not None:
        unconsumed = db.execute(select(func.count(M.FeedbackEvent.id)).where(
            M.FeedbackEvent.project_id == lens.project_id, M.FeedbackEvent.consumed_by_lens_version_id.is_(None),
            M.FeedbackEvent.kind != "lane_override", M.FeedbackEvent.at > cur.created_at)).scalar_one()
    ruler = db.execute(select(M.Ruler).order_by(M.Ruler.created_at.desc())).scalars().first()
    return S.LensOverview(
        id=lens.id, person=person_ref(pe), status=lens.status,
        consent=S.ConsentInfo(id=c.id, scope=c.scope, granted_by=c.granted_by, granted_at=c.granted_at,
                              revoked_at=c.revoked_at, text_version=c.text_version, synthetic=c.synthetic) if c else None,
        versions=[S.LensVersionRef(id=v.id, version=v.version, created_at=v.created_at, change_reason=v.change_reason,
                                   origin="snapshot" if v.origin == "snapshot" else "live", cutoff_at=v.cutoff_at,
                                   status=v.status, counts=_counts(db, v)) for v in versions],
        current_version=cur.version if cur else None, unconsumed_feedback=int(unconsumed),
        update_min_events=int(cfg.lens["feedback"]["update_min_events"]), health_state=_health(db, lens),
        ruler_changed=bool(cur and ruler and ruler.id != cur.ruler_id), owner_login=pe.login if pe else None,
        fictional=bool(p and p.fictional))


def get_lens(lid: str, ctx: Ctx) -> S.LensOverview:
    with session_scope() as db:
        return _overview(db, _lens(db, lid))


def get_version(lid: str, v: int, ctx: Ctx) -> S.LensVersionOut:
    with session_scope() as db:
        lens = _lens(db, lid)
        lv = _version(db, lens, v)
        pe = db.get(M.Person, lens.person_id)
        owner = _owner(ctx)
        card_md = lv.card_md or ""
        if lv.card:
            card_md = CARD.render(lv.card, pe, owner_view=owner, include_bias=owner)
        ruler = db.get(M.Ruler, lv.ruler_id)
        bs = dict(lv.build_stats or {})
        if "from" not in bs:
            first = db.execute(select(func.min(M.FindingRow.created_at)).where(
                M.FindingRow.person_id == lens.person_id, M.FindingRow.source == "human",
                M.FindingRow.context == "history", M.FindingRow.created_at <= lv.cutoff_at)).scalar()
            if first is not None:
                bs["from"] = first.isoformat()
        key_facts = {"cutoff": lv.cutoff_at.date().isoformat(), "reviews_used": bs.get("reviews"),
                     "prs_used": bs.get("prs"), "r_plus": bs.get("r_plus"), "r_minus": bs.get("r_minus"),
                     "shared": bs.get("shared")}
        return S.LensVersionOut(id=lv.id, version=lv.version, card_md=card_md, card=lv.card or {}, cutoff_at=lv.cutoff_at,
                                ruler_id=lv.ruler_id, ruler_display=get_config().model_display(ruler.spec["llm"]["model_id"])
                                if ruler else None, build_stats=bs, items_count=_counts(db, lv),
                                key_facts={k: x for k, x in key_facts.items() if x is not None},
                                change_reason=lv.change_reason,
                                provenance=provenance(lv.origin, lv.created_at, lv.ruler_id, lv.version, list(lv.models or [])))


def _edited(it: M.LensItemRow) -> tuple[str, str]:
    title, statement = it.title, it.statement
    for e in it.owner_edits or []:
        title = e.get("title", title)
        statement = e.get("statement", statement)
    return title, statement


def _item_out(db, it: M.LensItemRow) -> S.LensItemOut:  # type: ignore[no-untyped-def]
    st = it.stats or {}
    o = st.get("outcome") or {}
    ci = o.get("ci90")
    bc = db.execute(select(M.BiasCheck).where(M.BiasCheck.lens_item_id == it.id)).scalars().first()
    tr = it.triggers or {}
    title, statement = _edited(it)
    lcfg = get_config().lens
    return S.LensItemOut(
        id=it.id, stable_key=it.stable_key, type=it.type, title=title, statement_md=statement, rationale_md=it.rationale,
        category=it.category, category_label=V.category_label(it.category), severity_typical=it.severity_typical,
        triggers=S.TriggersOut(paths=tr.get("paths", []), code_patterns=tr.get("code_patterns", []),
                               counter_patterns=(tr.get("pr_features") or {}).get("counter_patterns", [])),
        stats=S.LensItemStats(support=int(st.get("support", 0)), trigger_precision=st.get("trigger_precision"),
                              baseline_overlap=st.get("baseline_overlap"), posterior_mean=o.get("posterior_mean"),
                              ci90=S.Interval(low=ci[0], high=ci[1]) if ci else None, n_ignored=int(o.get("ignored", 0)),
                              k_bad=int(o.get("bad_when_ignored", 0)), base_rate=o.get("base_rate"), lift=o.get("lift"),
                              first_seen=st.get("first_seen"), last_seen=st.get("last_seen"),
                              enough_evidence=int(st.get("support", 0)) >= int(lcfg["status"]["min_support"])),
        status=it.status, owner_override=it.owner_override, explanation=it.explanation,
        bias={"odds_ratio": bc.odds_ratio, "ci": [bc.ci_low, bc.ci_high], "verdict": bc.verdict} if bc else None,
        owner_only=it.status == "bias_suspected", provenance=it.provenance or {})


def list_items(lid: str, v: int, *, type: str | None, category: str | None, status: str | None, q: str | None,
               ctx: Ctx) -> S.LensItemList:
    with session_scope() as db:
        lens = _lens(db, lid)
        lv = _version(db, lens, v)
        rows = db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lv.id)).scalars().all()
        owner = _owner(ctx)
        out = []
        for it in rows:
            if not owner and it.status == "bias_suspected":
                continue
            if type and it.type != type or category and it.category != category or status and it.status != status:
                continue
            o = _item_out(db, it)
            if not owner:
                o.bias = None
            if q and q.lower() not in (o.title + " " + o.statement_md).lower():
                continue
            out.append(o)
        order = {"edge": 0, "blind_spot": 1, "shared_ground": 2}
        out.sort(key=lambda x: (order.get(x.type, 9), x.status != "validated", -x.stats.support))
        return S.LensItemList(items=out)


def get_item(item_id: str, ctx: Ctx) -> S.LensItemDetail:
    with session_scope() as db:
        it = db.get(M.LensItemRow, item_id)
        if it is None:
            raise NotFound("Lens item not found.")
        if it.status == "bias_suspected" and not _owner(ctx):
            raise Forbidden("Only the lens owner can see this item.")
        lv = db.get(M.LensVersion, it.lens_version_id)
        lens = db.get(M.Lens, lv.lens_id)
        p = db.get(M.Project, lens.project_id)
        ev = db.execute(select(M.LensItemEvidence).where(M.LensItemEvidence.lens_item_id == it.id)).scalars().all()
        exemplars = []
        for e in [e for e in ev if e.role == "exemplar"]:
            f = db.get(M.FindingRow, e.finding_id) if e.finding_id else None
            if f is None:
                continue
            pc = V.past_comment(db, f.id)
            hunk = None
            if (f.refs or {}).get("comment_ids"):
                rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == f.refs["comment_ids"][0])
                                ).scalars().first()
                hunk = "\n".join((rc.diff_hunk or "").split("\n")[-12:]) if rc and rc.diff_hunk else None
            exemplars.append(S.Exemplar(finding_id=f.id, pr_number=f.pr_number, statement=f.statement, path=f.path,
                                        line=f.start_line, hunk=hunk, comment_excerpt=pc.excerpt if pc else None,
                                        author=pc.author if pc else None, at=f.created_at,
                                        html_url=pc.html_url if pc else None))
        history = []
        for older in db.execute(select(M.LensItemRow, M.LensVersion).join(M.LensVersion).where(
                M.LensVersion.lens_id == lens.id, M.LensItemRow.stable_key == it.stable_key)
                .order_by(M.LensVersion.version)).all():
            row, ver = older
            history.append({"version": ver.version, "status": row.status, "support": (row.stats or {}).get("support"),
                            "hit_rate": (row.stats or {}).get("outcome", {}).get("posterior_mean")})
        for e in it.owner_edits or []:
            history.append({"edit": {k: x for k, x in e.items() if k != "at"}, "at": e.get("at")})
        o = (it.stats or {}).get("outcome") or {}
        outcomes = []
        for n in o.get("bad_prs", [])[:8]:
            pr = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.number == n)).scalars().first()
            outcomes.append({"pr_number": n, "title": pr.title if pr else "", "kind": "bad_outcome"})
        base = _item_out(db, it)
        if not _owner(ctx):
            base.bias = None
        return S.LensItemDetail(**base.model_dump(), exemplars=exemplars,
                                counter_examples=sorted(e.pr_number for e in ev if e.role == "counter_example" and e.pr_number),
                                history=history, outcomes=outcomes)


def patch_item(item_id: str, body: S.LensItemPatch, ctx: Ctx) -> S.LensItemOut:
    if not _owner(ctx):
        raise Forbidden("Only the lens owner can change items.")
    with session_scope() as db:
        it = db.get(M.LensItemRow, item_id)
        if it is None:
            raise NotFound("Lens item not found.")
        lv = db.get(M.LensVersion, it.lens_version_id)
        lens = db.get(M.Lens, lv.lens_id)
        now = datetime.now(UTC)
        if body.status == "muted":
            it.owner_override = "mute"
            it.status = "disabled_by_owner"
        elif body.status == "active":
            it.owner_override = "keep" if it.status == "bias_suspected" else None
            if it.status in ("disabled_by_owner", "bias_suspected"):
                it.status = "validated"
        if body.not_me:
            it.owner_override = "not_me"
            it.status = "disabled_by_owner"
        if body.edits:
            allowed = {k: x.strip() for k, x in body.edits.items() if k in ("title", "statement") and x.strip()}
            if not allowed:
                raise ValidationFailed("Only the title and statement can be edited.")
            it.owner_edits = [*(it.owner_edits or []), {**allowed, "at": now.isoformat()}]
        db.add(M.FeedbackEvent(id=new_id("fbk"), project_id=lens.project_id, pr_number=0, kind="lens_item_edit",
                               payload={"item_id": it.id, "stable_key": it.stable_key, "status": body.status,
                                        "edits": body.edits, "not_me": body.not_me, "reason": body.reason},
                               lens_version_id=lv.id, ruler_id=lv.ruler_id))
        R.audit(db, ctx.role, "lens_item_changed", "lens_item", it.id, {"status": body.status, "not_me": body.not_me,
                                                                       "edited": bool(body.edits), "reason": body.reason})
        db.flush()
        return _item_out(db, it)


def _as_dicts(db, lv: M.LensVersion) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    rows = db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lv.id)).scalars().all()
    return [{"id": r.id, "stable_key": r.stable_key, "type": r.type, "title": _edited(r)[0], "statement": _edited(r)[1],
             "category": r.category, "status": r.status, "stats": r.stats or {}} for r in rows]


CHANGE_TEXT = {"added": "New", "retired": "Retired", "reworded": "Reworded", "strengthened": "Stronger",
               "weakened": "Weaker", "status_changed": "Status changed", "blind_spot_closed": "Blind spot closed"}


def diff(lid: str, from_: int | None, to: int | None, ctx: Ctx) -> S.LensDiff:
    with session_scope() as db:
        lens = _lens(db, lid)
        b = _version(db, lens, to)
        if from_ is None:
            a = db.get(M.LensVersion, b.parent_version_id) if b.parent_version_id else None
            if a is None:
                a = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id,
                                                           M.LensVersion.version < b.version)
                               .order_by(M.LensVersion.version.desc())).scalars().first()
            if a is None:
                raise NotFound("There is no earlier version to compare with.")
        else:
            a = _version(db, lens, from_)
        owner = _owner(ctx)
        changes = LD.diff(_as_dicts(db, a), _as_dicts(db, b), get_config().lens)
        buckets: dict[str, list[S.LensDiffEntry]] = {"added": [], "removed": [], "changed": []}
        for c in changes:
            it = c["item"]
            if not owner and it["status"] == "bias_suspected":
                continue
            detail = None
            if c["change"] in ("strengthened", "weakened"):
                detail = f"support {c['from']['support']} → {c['to']['support']}"
            elif c["change"] == "status_changed":
                detail = f"{c['from']} → {c['to']}"
            elif c["change"] == "reworded":
                detail = f"was: {c['from']}"
            e = S.LensDiffEntry(change=c["change"], item_id=it["id"], stable_key=it["stable_key"], title=it["title"],
                                category=it["category"], detail=detail,
                                fields={k: {"from": c.get("from"), "to": c.get("to")} for k in ("value",) if "from" in c})
            key = "added" if c["change"] == "added" else "removed" if c["change"] in ("retired", "blind_spot_closed") \
                else "changed"
            buckets[key].append(e)
        pe = db.get(M.Person, lens.person_id)
        lines = [f"From v{a.version} to v{b.version} of {name_of(pe)}'s lens: {len(buckets['added'])} new, "
                 f"{len(buckets['changed'])} changed, {len(buckets['removed'])} retired."]
        for e in (buckets["added"] + buckets["changed"] + buckets["removed"])[:8]:
            lines.append(f"- {CHANGE_TEXT.get(e.change, e.change)}: {e.title}" + (f" ({e.detail})" if e.detail else ""))
        return S.LensDiff(from_version=a.version, to_version=b.version, added=buckets["added"],
                          removed=buckets["removed"], changed=buckets["changed"], summary_md="\n".join(lines),
                          summary_simulated=False)


def _action(lid: str, body: S.LensActionRequest, ctx: Ctx, kind: str, est_key: str, label: str) -> S.JobAccepted:
    if not _owner(ctx):
        raise Forbidden("Only the lens owner can change the lens.")
    require_live()
    with session_scope() as db:
        lens = _lens(db, lid)
        if lens.status == "revoked":
            raise Conflict("This lens was revoked.")
        pid = lens.project_id
    confirm(kind, {"lid": lid}, estimate(est_key), body.confirm_token, label)
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit(kind, {"project_id": pid, "lens_id": lid, "reason": body.reason},
                                        key=f"{kind}:{lid}")
    return job_ref(jid, kind, existing)


def rebuild(lid: str, body: S.LensActionRequest, ctx: Ctx) -> S.JobAccepted:
    return _action(lid, body, ctx, "learn", "lens_build", "Rebuild the lens from all reviews")


def update(lid: str, body: S.LensActionRequest, ctx: Ctx) -> S.JobAccepted:
    return _action(lid, body, ctx, "lens_update", "lens_update", "Update the lens with your feedback")


def recalibrate(lid: str, body: S.LensActionRequest, ctx: Ctx) -> S.JobAccepted:
    return _action(lid, body, ctx, "recalibrate", "recalibrate", "Recalibrate the lens against outcomes")


def set_status(lid: str, status: str, ctx: Ctx) -> S.LensOverview:
    if not _owner(ctx):
        raise Forbidden("Only the lens owner can pause or resume it.")
    with session_scope() as db:
        lens = _lens(db, lid)
        if lens.status == "revoked":
            raise Conflict("This lens was revoked.")
        GOV.set_status(db, lens, status, ctx.role)
        db.flush()
        return _overview(db, lens)


def revoke(lid: str, body: S.RevokeRequest, ctx: Ctx) -> S.LensOverview:
    if not _owner(ctx):
        raise Forbidden("Only the lens owner can revoke it.")
    with session_scope() as db:
        lens = _lens(db, lid)
        pe = db.get(M.Person, lens.person_id)
        if body.confirm.strip().upper() != "REVOKE" or (body.typed_login or "").strip() != pe.login:
            raise ValidationFailed("Type REVOKE and the person's login to confirm.")
        GOV.revoke(db, lens, ctx.role)
        db.flush()
        return _overview(db, lens)


def export(lid: str, *, include_exemplars: bool, include_bias: bool, fmt: str, ctx: Ctx) -> tuple[str, bytes, str]:
    if not _owner(ctx):
        raise Forbidden("Only the lens owner can export it.")
    cfg = get_config()
    with session_scope() as db:
        lens = _lens(db, lid)
        lv = _version(db, lens, None)
        pe = db.get(M.Person, lens.person_id)
        card_md = CARD.plain(CARD.render(lv.card, pe, include_bias=include_bias) if lv.card else (lv.card_md or ""))
        if fmt == "md":
            return f"{pe.login}-lens-v{lv.version}.md", card_md.encode(), "text/markdown"
        rows = db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lv.id)).scalars().all()
        items = []
        for r in rows:
            if r.status in ("disabled_by_owner", "retired"):
                continue
            title, statement = _edited(r)
            bc = db.execute(select(M.BiasCheck).where(M.BiasCheck.lens_item_id == r.id)).scalars().first()
            o = (r.stats or {}).get("outcome") or {}
            it = {"id": r.stable_key, "type": r.type, "title": title, "statement": statement, "category": r.category,
                  "severity_typical": r.severity_typical, "status": r.status,
                  "triggers": {"paths": (r.triggers or {}).get("paths", []),
                               "code_patterns": (r.triggers or {}).get("code_patterns", [])},
                  "stats": {"support": int((r.stats or {}).get("support", 0)),
                            "hit_rate": o.get("posterior_mean"), "ci90": o.get("ci90")}}
            if bc:
                it["bias"] = {"odds_ratio": bc.odds_ratio, "verdict": bc.verdict}
            items.append(it)
        exemplars = None
        if include_exemplars:
            ids = [e.finding_id for e in db.execute(select(M.LensItemEvidence).where(
                M.LensItemEvidence.lens_item_id.in_([r.id for r in rows]), M.LensItemEvidence.role == "exemplar"))
                .scalars() if e.finding_id]
            exemplars = [{"pr_number": f.pr_number, "path": f.path, "statement": f.statement}
                         for i in ids if (f := db.get(M.FindingRow, i))]
        version = {"version": lv.version, "cutoff_at": lv.cutoff_at.isoformat(), "ruler_id": lv.ruler_id,
                   "change_reason": lv.change_reason, "models": list(lv.models or [])}
        prov = {"exported_at": datetime.now(UTC).isoformat(), "project": lens.project_id, "lens_id": lens.id,
                "models": list(lv.models or []), "origin": lv.origin}
        data = PKG.build(pe.login, version, items, card_md, exemplars,
                         cfg.lens["package"]["licence"].format(person=pe.login), prov, include_bias=include_bias)
        R.audit(db, ctx.role, "lens_exported", "lens", lens.id, {"version": lv.version, "exemplars": include_exemplars,
                                                                 "bias": include_bias})
        return f"{pe.login}-lens-v{lv.version}.zip", data, "application/zip"


def import_package(pid: str, data: bytes, filename: str, ctx: Ctx) -> S.LensOverview:
    if not _owner(ctx):
        raise Forbidden("Only the maintainer role can import a lens.")
    if len(data) > int(get_config().lens["package"]["max_bytes"]):
        raise ValidationFailed("The package is larger than 5 MB.")
    try:
        pkg = PKG.read(data)
    except Exception as e:  # noqa: BLE001
        raise ValidationFailed(f"This isn't a Keeper lens package: {e}") from e
    lj = pkg["lens"]
    with session_scope() as db:
        p = project(db, pid)
        login = lj["person"]
        pe = db.execute(select(M.Person).where(M.Person.project_id == p.id, M.Person.login == login)).scalars().first()
        if pe is None:
            pe = M.Person(id=stable_id("per", p.id, login), project_id=p.id, login=login, role="reviewer")
            db.add(pe)
            db.flush()
        c = GOV.active_consent(db, p.id, pe.id) or GOV.grant(db, p.id, pe.id, "build_lens", "import")
        lens = db.execute(select(M.Lens).where(M.Lens.project_id == p.id, M.Lens.person_id == pe.id)).scalars().first()
        if lens is None:
            lens = M.Lens(id=stable_id("lns", p.id, pe.id), person_id=pe.id, project_id=p.id, status="active",
                          consent_id=c.id)
            db.add(lens)
            db.flush()
        elif lens.status == "revoked":
            lens.status, lens.consent_id = "active", c.id
        n = (db.execute(select(func.max(M.LensVersion.version)).where(M.LensVersion.lens_id == lens.id)).scalar() or 0) + 1
        ver = lj.get("version") or {}
        cutoff = datetime.fromisoformat(ver["cutoff_at"]) if ver.get("cutoff_at") else datetime.now(UTC)
        lv = M.LensVersion(id=new_id("lv"), lens_id=lens.id, version=n, cutoff_at=cutoff,
                           ruler_id=ver.get("ruler_id") or "imported", change_reason="imported", status="ready",
                           card_md=pkg["card_md"], card={}, build_stats={"imported_from": filename}, origin="live")
        db.add(lv)
        db.flush()
        for it in lj["items"]:
            st = it.get("stats") or {}
            db.add(M.LensItemRow(id=new_id("li"), lens_version_id=lv.id, stable_key=it["id"], type=it["type"],
                                 title=it["title"], statement=it["statement"], category=it["category"],
                                 severity_typical=it.get("severity_typical", "minor"),
                                 triggers={"paths": it.get("triggers", {}).get("paths", []),
                                           "code_patterns": it.get("triggers", {}).get("code_patterns", [])},
                                 stats={"support": st.get("support", 0),
                                        "outcome": {"posterior_mean": st.get("hit_rate"), "ci90": st.get("ci90")}},
                                 status=it.get("status", "candidate"), provenance={"imported_from": filename}))
        R.audit(db, ctx.role, "lens_imported", "lens", lens.id, {"version": n, "items": len(lj["items"])})
        db.flush()
        return _overview(db, lens)


def edge_map(lid: str, version: int | None) -> S.EdgeMapOut:
    with session_scope() as db:
        lens = _lens(db, lid)
        lv = _version(db, lens, version)
        p = db.get(M.Project, lens.project_id)
        pe = db.get(M.Person, lens.person_id)
        items = list(V.items_of(db, lv.id).values())
        open_prs = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.state == "open")).scalars().all()
        files_of = {pr.number: [f.filename for f in db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id))
                                .scalars()] for pr in open_prs}
        from keeper.find.edge_map import area_for_path
        depth = int(get_config().find["area_depth"])
        cells = []
        for c in db.execute(select(M.EdgeMapCell).where(M.EdgeMapCell.lens_version_id == lv.id)).scalars():
            its = [S.LensItemRef(id=i.id, title=_edited(i)[0], status=i.status, support=(i.stats or {}).get("support"))
                   for i in items if i.category == c.category and i.type != "shared_ground" and
                   any(area_for_path(g.replace("*", "x"), depth) == c.area for g in (i.triggers or {}).get("paths", []))]
            opens = sorted(n for n, fs in files_of.items() if any(area_for_path(f, depth) == c.area for f in fs))
            d = c.details or {}
            cells.append(S.EdgeCell(area=c.area, category=c.category, category_label=V.category_label(c.category)
                                    if c.category else "", volume=c.volume, residual_rate=c.residual_rate,
                                    shared_rate=c.shared_rate, cost=c.cost, value=c.value, kind=c.kind,
                                    multiplier=d.get("multiplier"), bad_outcomes=d.get("bad", []), items=its,
                                    open_prs=opens, findings=int(d.get("findings", 0))))
        top = sorted([c for c in cells if c.kind == "top"], key=lambda c: -c.value)
        enough = [c for c in cells if c.kind == "enough"]
        gaps = [c for c in cells if c.kind == "gap"]
        name = name_of(pe)
        lines = [f"Where {name}'s attention is worth most:"]
        lines += [f"- **{c.area}** · {c.category_label} (value {c.value:.2f})" for c in top[:5]]
        if enough:
            lines.append("Generic review is already enough in: " + ", ".join(sorted({c.area for c in enough})[:6]) + ".")
        if gaps:
            lines.append("No one has much review history in: " + ", ".join(sorted({c.area for c in gaps})[:6]) + ".")
        return S.EdgeMapOut(cells=cells, top=top, enough=enough, gaps=gaps, areas=sorted({c.area for c in cells}),
                            categories=sorted({c.category for c in cells if c.category}), summary_md="\n".join(lines))


def bias(lid: str, ctx: Ctx) -> S.BiasList:
    if not _owner(ctx):
        return S.BiasList(items=[])
    cfg = get_config()
    with session_scope() as db:
        lens = _lens(db, lid)
        lv = _version(db, lens, None)
        items = V.items_of(db, lv.id)
        out = []
        expl = cfg.lens["bias"].get("explanations", {})
        for bc in db.execute(select(M.BiasCheck).where(M.BiasCheck.lens_item_id.in_(list(items)))).scalars():
            it = items[bc.lens_item_id]
            text = expl.get(bc.verdict)
            if text is None and bc.verdict == "bias_suspected":
                text = (f"On PRs where this applies, newcomers were flagged about {bc.odds_ratio:.1f}× as often as "
                        "regular contributors of similar size and area, and the extra flags didn't predict worse "
                        "outcomes. Keeper stopped using it; you can keep it if it's deliberate.")
            out.append(S.BiasOut(item_id=it.id, title=_edited(it)[0], odds_ratio=bc.odds_ratio,
                                 ci=S.Interval(low=bc.ci_low, high=bc.ci_high) if bc.ci_low is not None and
                                 bc.ci_high is not None else None, verdict=bc.verdict, n_by_group=bc.n_by_group or {},
                                 outcome_check=bc.outcome_check or {}, explanation_md=text))
        out.sort(key=lambda b: (b.verdict != "bias_suspected", -(b.odds_ratio or 0)))
        return S.BiasList(items=out)


def growth(lid: str) -> S.GrowthOut:
    cfg = get_config()
    with session_scope() as db:
        lens = _lens(db, lid)
        snaps = db.execute(select(M.GrowthSnapshot).where(M.GrowthSnapshot.lens_id == lens.id)
                           .order_by(M.GrowthSnapshot.period_start)).scalars().all()
        live = [s for s in snaps if s.origin == "live"]
        snaps = live or snaps
        state = snaps[-1].health_state if snaps else "insufficient_data"
        gids = (snaps[-1].measures or {}).get("g_examples", []) if snaps else []
        pe = db.get(M.Person, lens.person_id)
        g = [V.finding_out(db, f, pe.login if pe else None) for i in gids if (f := db.get(M.FindingRow, i))]
        periods = [S.GrowthPeriod(period=f"{s.period_start.date().isoformat()} – {s.period_end.date().isoformat()}",
                                  period_start=s.period_start, period_end=s.period_end,
                                  measures={k: x for k, x in (s.measures or {}).items() if k != "g_examples"},
                                  state=s.health_state) for s in snaps]
        last = snaps[-1].measures if snaps else {}
        return S.GrowthOut(health_state=state or "insufficient_data",
                           explanation_md=cfg.growth.get("explanations", {}).get(state or "insufficient_data", ""),
                           snapshots=periods, g_examples=g, accepted_share=(last or {}).get("assisted_share"))


def audit(lid: str) -> S.AuditList:
    with session_scope() as db:
        lens = _lens(db, lid)
        vids = [v for (v,) in db.execute(select(M.LensVersion.id).where(M.LensVersion.lens_id == lens.id))]
        iids = [i for (i,) in db.execute(select(M.LensItemRow.id).where(M.LensItemRow.lens_version_id.in_(vids)))]
        objs = [lens.id, lens.person_id, *vids, *iids]
        rows = db.execute(select(M.AuditEvent).where(M.AuditEvent.object_id.in_(objs))
                          .order_by(M.AuditEvent.at.desc()).limit(200)).scalars().all()
        return S.AuditList(items=[S.AuditOut(at=r.at, actor_role=r.actor_role, action=r.action,
                                             object_type=r.object_type, object_id=r.object_id, details=r.details or {})
                                  for r in rows])

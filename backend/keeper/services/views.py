"""Mappers from rows to API shapes, shared by the PR, queue, proof and assistant services."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.app import schemas as S
from keeper.config import get_config
from keeper.core.types import RiskSignal
from keeper.db import models as M
from keeper.db import repo as R
from keeper.route.lanes import apply_override
from keeper.services.common import prefer_live, provenance


def category_label(cat: str) -> str:
    return str(get_config().taxonomy["categories"].get(cat, {}).get("label", cat))


def anchor(f: M.FindingRow) -> S.AnchorOut:
    return S.AnchorOut(scope=f.scope, path=f.path, side=f.side or "RIGHT", start_line=f.start_line, end_line=f.end_line)


def finding_out(db: Session, f: M.FindingRow, person_login: str | None = None) -> S.FindingOut:
    url = None
    if f.source == "human" and (f.refs or {}).get("comment_ids"):
        rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == f.refs["comment_ids"][0])).scalars().first()
        url = rc.html_url if rc else None
    return S.FindingOut(id=f.id, source=f.source, person=person_login, title=f.title or R.short_title(f.statement),
                        statement=f.statement, category=f.category, category_label=category_label(f.category),
                        severity=f.severity, kind=f.kind, anchor=anchor(f), confidence=f.confidence,
                        substantive=f.substantive, lens_item_ids=list((f.refs or {}).get("lens_item_ids", [])),
                        exemplar_ids=list((f.refs or {}).get("exemplar_finding_ids", [])), html_url=url,
                        created_at=f.created_at)


def past_comment(db: Session, fid: str) -> S.PastComment | None:
    f = db.get(M.FindingRow, fid)
    if f is None:
        return None
    excerpt = f.statement
    url = None
    author = None
    if (f.refs or {}).get("comment_ids"):
        rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == f.refs["comment_ids"][0])).scalars().first()
        if rc:
            excerpt, url = rc.body[:280], rc.html_url
    if f.person_id:
        pe = db.get(M.Person, f.person_id)
        author = pe.login if pe else None
    return S.PastComment(id=f.id, pr_number=f.pr_number, excerpt=excerpt, path=f.path, at=f.created_at, author=author,
                         html_url=url)


def signals_of(a: M.Analysis) -> list[RiskSignal]:
    return [RiskSignal(**s) for s in (a.signals or [])]


def signal_refs(a: M.Analysis) -> list[S.SignalRef]:
    return [S.SignalRef(key=s.key, label=s.label, severity=s.severity, covered=s.covered, paths=s.paths,
                        evidence=s.evidence) for s in signals_of(a)]


def current_analysis(db: Session, project_id: str, pr: M.Pull, purposes: tuple[str, ...] = ("queue",)
                     ) -> M.Analysis | None:
    rows = db.execute(select(M.Analysis).where(M.Analysis.project_id == project_id, M.Analysis.pr_number == pr.number,
                                               M.Analysis.purpose.in_(purposes))).scalars().all()
    at_head = [r for r in rows if r.head_sha == pr.head_sha] or rows
    return prefer_live(at_head)


def lane_override(db: Session, project_id: str, n: int) -> str | None:
    ev = db.execute(select(M.FeedbackEvent).where(M.FeedbackEvent.project_id == project_id,
                                                  M.FeedbackEvent.pr_number == n, M.FeedbackEvent.kind == "lane_override")
                    .order_by(M.FeedbackEvent.at.desc())).scalars().first()
    return (ev.payload or {}).get("lane") if ev else None


def effective_lane(db: Session, project_id: str, a: M.Analysis) -> str:
    return apply_override(a.pr_lane, lane_override(db, project_id, a.pr_number), signals_of(a))


def routed_out(db: Session, a: M.Analysis, rf: M.RoutedFindingRow, items: dict[str, M.LensItemRow]) -> S.RoutedFindingOut | None:
    cfg = get_config()
    f = db.get(M.FindingRow, rf.finding_id)
    if f is None:
        return None
    paired = db.get(M.FindingRow, rf.paired_finding_id) if rf.paired_finding_id else None
    source = "both" if paired is not None else ("lens" if f.source == "lens" else "baseline")
    lens_items = []
    for iid in (f.refs or {}).get("lens_item_ids", []):
        it = items.get(iid)
        if it is not None:
            lens_items.append(S.LensItemRef(id=it.id, title=it.title, status=it.status, support=(it.stats or {}).get("support")))
    past = [pc for e in (f.refs or {}).get("exemplar_finding_ids", [])[:4] if (pc := past_comment(db, e))]
    bs = None
    if rf.blind_spot_item_id and rf.blind_spot_item_id in items:
        it = items[rf.blind_spot_item_id]
        o = (it.stats or {}).get("outcome", {})
        bs = S.BlindSpotEvidence(id=it.id, title=it.title, bad_outcomes=int(o.get("bad_when_ignored", 0)),
                                 ignored=int(o.get("ignored", 0)), outcome_prs=list(o.get("bad_prs", []))[:5])
    mm = (a.stats or {}).get("model_meta", {})
    m = mm.get("lens") if f.source == "lens" else mm.get("baseline")
    model = S.ModelTag(model_id=m.get("model"), display=m.get("model_display"), latency_ms=m.get("latency_ms")) if m else None
    sig = [s.label for s in signals_of(a)] if rf.lane in ("edge", "blind_spot") else []
    return S.RoutedFindingOut(
        id=rf.id, finding_id=f.id, lane=rf.lane, action=rf.action, source=source,
        title=(f.title or R.short_title(f.statement)), statement_md=rf.user_text or f.statement,
        rationale_md=f.rationale, suggestion_md=f.suggestion, category=f.category,
        category_label=category_label(f.category), severity=rf.user_severity or f.severity, kind=f.kind,
        anchor=anchor(f), confidence=f.confidence if f.confidence in ("high", "medium", "low") else None,
        fixable=bool(rf.fixable and cfg.fixable(f.category)),
        evidence=S.FindingEvidence(lens_items=lens_items, past_comments=past,
                                   baseline_pair=S.BaselinePair(finding_id=paired.id, statement=paired.statement,
                                                                decision=(rf.evidence or {}).get("decision"))
                                   if paired else None, blind_spot_item=bs, signals=sig,
                                   why_similar=(f.refs or {}).get("why_similar"), tool=(f.refs or {}).get("tool")),
        model=model, user_state=rf.user_state, user_text=rf.user_text, user_severity=rf.user_severity)


def items_of(db: Session, lens_version_id: str | None) -> dict[str, M.LensItemRow]:
    if not lens_version_id:
        return {}
    return {i.id: i for i in db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == lens_version_id))
            .scalars()}


def analysis_provenance(db: Session, a: M.Analysis) -> S.Provenance:
    lv = db.get(M.LensVersion, a.lens_version_id) if a.lens_version_id else None
    return provenance(a.origin, a.created_at, a.ruler_id, lv.version if lv else None, list(a.models or []))


_ = Any

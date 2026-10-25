"""The assistant's tools (docs/04-architecture/06-assistant.md §2). Read tools call keeper.services with the same
permission checks as the API; action tools only return a proposal card that the user confirms in the UI."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import NotFound
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.services import views as V
from keeper.services.common import current_version, estimate, lens_of, maintainer, project

API = "/api/v1"


class Empty(BaseModel):
    pass


class QueueArgs(BaseModel):
    lane: str | None = Field(default=None, description="edge | blind_spot | unknown | shared")
    limit: int | None = Field(default=10, ge=1, le=50)


class NumberArgs(BaseModel):
    number: int


class FindingArgs(BaseModel):
    finding_id: str


class SearchArgs(BaseModel):
    query: str
    author: str | None = None
    path: str | None = None
    since: str | None = Field(default=None, description="ISO date")


class LensArgs(BaseModel):
    person: str | None = Field(default=None, description="login; the maintainer by default")
    version: int | None = None


class ItemArgs(BaseModel):
    item_id: str


class DiffArgs(BaseModel):
    from_: int | None = Field(default=None, alias="from")
    to: int | None = None
    model_config = {"populate_by_name": True}


class ProofArgs(BaseModel):
    run_id: str | None = None


class PersonArgs(BaseModel):
    person: str | None = None


class UsageArgs(BaseModel):
    period: str | None = Field(default="month", description="day | week | month | all")


class TermArgs(BaseModel):
    term: str


class FixArgs(BaseModel):
    number: int
    finding_ids: list[str]


class ReasonArgs(BaseModel):
    reason: str | None = None


class PracticeArgs(BaseModel):
    person: str | None = None
    length: int | None = None


@dataclass
class Tool:
    name: str
    kind: str  # read | action
    description: str
    args: type[BaseModel]
    label: Callable[[dict[str, Any]], str]
    run: Callable[[Any, Ctx, str], tuple[dict[str, Any], list[dict[str, Any]]]]


def _card(t: str, **data: Any) -> dict[str, Any]:
    return {"type": t, "data": data}


def _clip(s: str | None, n: int = 280) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ----------------------------------------------------------------------------------------------- read tools
def get_queue(a: QueueArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import queue
    q = queue.get_queue(pid, lane=a.lane)
    rows = q.items[: a.limit or 10]
    s = q.summary
    res = {"summary": {"by_lane": s.by_lane.model_dump(), "attention_minutes_total": s.attention_minutes_total,
                       "budget_minutes": s.budget_minutes, "need_count": s.need_count, "total": s.total,
                       "naive_minutes": s.naive_minutes},
           "rows": [{"number": r.number, "title": r.title, "lane": r.lane, "reasons": [x.label for x in r.reasons][:3],
                     "attention_minutes": r.attention_minutes, "author": r.author.login,
                     "signals": [x.label for x in r.signals]} for r in rows]}
    cards = [_card("pull", number=r.number, title=r.title, lane=r.lane, reason=r.reasons[0].label if r.reasons else "")
             for r in rows]
    return res, cards


def _finding_card(f: Any, number: int) -> dict[str, Any]:
    return _card("finding", id=f.id, title=f.title, lane=f.lane, number=number,
                 anchor={"path": f.anchor.path, "line": f.anchor.start_line})


def get_pull(a: NumberArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import pulls
    pr = pulls.get_pull(pid, a.number)
    res: dict[str, Any] = {"number": pr.number, "title": pr.title, "author": pr.author.login, "state": pr.state,
                           "files": [f.filename for f in pr.files][:20], "body": _clip(pr.body_md, 600)}
    cards = []
    try:
        an = pulls.get_analysis(pid, a.number, ctx)
        res.update({"lane": an.lane, "summary": an.summary_md, "attention_minutes": an.attention_minutes,
                    "signals": [{"label": s.label, "covered": s.covered} for s in an.signals],
                    "reasons": [r.label for r in an.reasons],
                    "findings": [{"id": f.id, "lane": f.lane, "title": f.title, "path": f.anchor.path,
                                  "line": f.anchor.start_line, "category": f.category_label, "fixable": f.fixable,
                                  "source": f.source} for f in an.findings if f.user_state != "dismissed"]})
        cards.append(_card("pull", number=pr.number, title=pr.title, lane=an.lane,
                           reason=an.reasons[0].label if an.reasons else ""))
        cards += [_finding_card(f, pr.number) for f in an.findings]
    except NotFound:
        res["lane"] = None
        cards.append(_card("pull", number=pr.number, title=pr.title, lane="unknown", reason="Not sorted yet"))
    try:
        from keeper.services import fixes
        fx = fixes.list_fixes(pid, a.number).items
        if fx:
            res["fix"] = {"status": fx[0].status, "iterations": fx[0].iterations}
    except NotFound:
        pass
    return res, cards


def get_finding(a: FindingArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    with session_scope() as db:
        rf = db.get(M.RoutedFindingRow, a.finding_id)
        if rf is None:
            raise NotFound("Finding not found.")
        an = db.get(M.Analysis, rf.analysis_id)
        o = V.routed_out(db, an, rf, V.items_of(db, an.lens_version_id))
        if o is None:
            raise NotFound("Finding not found.")
        res = {"id": o.id, "pr": an.pr_number, "lane": o.lane, "title": o.title, "statement": o.statement_md,
               "rationale": o.rationale_md, "category": o.category_label, "severity": o.severity,
               "path": o.anchor.path, "line": o.anchor.start_line,
               "lens_items": [{"id": i.id, "title": i.title, "support": i.support} for i in o.evidence.lens_items],
               "past_comments": [{"id": c.id, "pr": c.pr_number, "excerpt": _clip(c.excerpt, 200), "author": c.author}
                                 for c in o.evidence.past_comments],
               "generic_review_pair": o.evidence.baseline_pair.statement if o.evidence.baseline_pair else None}
        cards = [_finding_card(o, an.pr_number)]
        cards += [_card("lens_item", id=i.id, title=i.title, kind="edge", support=i.support) for i in o.evidence.lens_items]
        cards += [_card("comment", id=c.id, author=c.author, at=c.at.isoformat() if c.at else None,
                        excerpt=_clip(c.excerpt, 240), pr_number=c.pr_number) for c in o.evidence.past_comments]
        return res, cards


_TOK = re.compile(r"[a-z0-9_]+")


def search_history(a: SearchArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from rank_bm25 import BM25Okapi
    with session_scope() as db:
        p = project(db, pid)
        people = {x.id: x.login for x in db.execute(select(M.Person).where(M.Person.project_id == p.id)).scalars()}
        q = select(M.ReviewComment).where(M.ReviewComment.project_id == p.id)
        rows = db.execute(q).scalars().all()
        if a.author:
            rows = [r for r in rows if people.get(r.author_id or "") == a.author.lstrip("@")]
        if a.path:
            rows = [r for r in rows if r.path and a.path in r.path]
        if a.since:
            try:
                since = datetime.fromisoformat(a.since).replace(tzinfo=UTC)
                rows = [r for r in rows if r.created_at and r.created_at >= since]
            except ValueError:
                pass
        if not rows:
            return {"results": []}, []
        docs = [_TOK.findall(((r.body or "") + " " + (r.path or "")).lower()) for r in rows]
        bm = BM25Okapi(docs)
        scores = bm.get_scores(_TOK.findall(a.query.lower()))
        top = sorted(range(len(rows)), key=lambda i: -scores[i])[:8]
        out, cards = [], []
        for i in top:
            if scores[i] <= 0:
                continue
            r = rows[i]
            cid = f"rc_{r.gh_id}"
            item = {"id": cid, "pr": r.pr_number, "author": people.get(r.author_id or ""), "path": r.path,
                    "at": r.created_at.date().isoformat() if r.created_at else None, "excerpt": _clip(r.body, 240)}
            out.append(item)
            cards.append(_card("comment", id=cid, author=item["author"], at=r.created_at.isoformat() if r.created_at
                               else None, excerpt=item["excerpt"], pr_number=r.pr_number, html_url=r.html_url))
        return {"results": out}, cards


def _lens_id(pid: str, person: str | None) -> str:
    with session_scope() as db:
        p = project(db, pid)
        pe = maintainer(db, p) if not person else db.execute(select(M.Person).where(
            M.Person.project_id == p.id, M.Person.login == person.lstrip("@"))).scalars().first()
        lens = lens_of(db, p, pe.id) if pe else None
        if lens is None:
            raise NotFound("No lens for this person.")
        return lens.id


def get_lens(a: LensArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import lens as L
    lid = _lens_id(pid, a.person)
    ov = L.get_lens(lid, ctx)
    v = a.version or ov.current_version
    if v is None:
        return {"status": ov.status, "versions": []}, []
    ver = L.get_version(lid, v, ctx)
    items = L.list_items(lid, v, type=None, category=None, status=None, q=None, ctx=ctx).items
    top = [i for i in items if i.type != "shared_ground"][:12]
    res = {"person": ov.person.login, "status": ov.status, "version": v, "health": ov.health_state,
           "versions": [x.version for x in ov.versions], "card": _clip(ver.card_md, 1500), "counts": ver.items_count,
           "items": [{"id": i.id, "type": i.type, "title": i.title, "status": i.status, "category": i.category_label,
                      "support": i.stats.support, "hit_rate": i.stats.posterior_mean} for i in top],
           "shared_ground": [i.title for i in items if i.type == "shared_ground"][:8]}
    cards = [_card("lens_item", id=i.id, title=i.title, kind=i.type, support=i.stats.support) for i in top]
    return res, cards


def get_lens_item(a: ItemArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import lens as L
    it = L.get_item(a.item_id, ctx)
    res = {"id": it.id, "type": it.type, "title": it.title, "statement": it.statement_md, "status": it.status,
           "category": it.category_label, "support": it.stats.support, "hit_rate": it.stats.posterior_mean,
           "triggers": it.triggers.model_dump(), "explanation": it.explanation,
           "exemplars": [{"pr": e.pr_number, "path": e.path, "excerpt": _clip(e.comment_excerpt or e.statement, 200)}
                         for e in it.exemplars[:5]], "counter_examples": it.counter_examples[:8]}
    cards = [_card("lens_item", id=it.id, title=it.title, kind=it.type, support=it.stats.support)]
    cards += [_card("comment", id=e.finding_id, author=e.author, at=e.at.isoformat() if e.at else None,
                    excerpt=_clip(e.comment_excerpt or e.statement, 240), pr_number=e.pr_number) for e in it.exemplars[:5]]
    return res, cards


def diff_lens_versions(a: DiffArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import lens as L
    d = L.diff(_lens_id(pid, None), a.from_, a.to, ctx)
    res = {"from": d.from_version, "to": d.to_version, "summary": d.summary_md,
           "added": [{"id": e.item_id, "title": e.title} for e in d.added],
           "removed": [{"id": e.item_id, "title": e.title} for e in d.removed],
           "changed": [{"id": e.item_id, "title": e.title, "change": e.change, "detail": e.detail} for e in d.changed]}
    cards = [_card("lens_item", id=e.item_id, title=e.title, kind="edge") for e in d.added + d.changed + d.removed]
    return res, cards


def get_proof(a: ProofArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import proof
    rid = a.run_id
    if rid is None:
        runs = proof.list_runs(pid).items
        if not runs:
            return {"runs": []}, []
        rid = runs[0].id
    r = proof.get_run(rid)
    k, b = r.metrics.get("keeper"), r.metrics.get("baseline")
    res = {"run_id": r.id, "lens_version": r.lens_version, "pass": r.pass_overall, "prs": r.cases_count,
           "simulated": r.provenance.simulated,
           "keeper_recall": k.substantive_recall.value if k else None,
           "generic_recall": b.substantive_recall.value if b else None,
           "difference": r.paired_difference.model_dump(), "noise_per_pr": {
               "keeper": k.noise_per_pr.value if k else None, "generic": b.noise_per_pr.value if b else None},
           "criteria": [{"label": c.label, "passed": c.passed, "detail": c.detail} for c in r.criteria],
           "falsifiers": [{"name": f.name, "result": f.result} for f in r.falsifiers]}
    cards = [_card("metric", name="recall_difference", label="Keeper minus generic recall",
                   value=r.paired_difference.value, interval={"low": r.paired_difference.low,
                                                              "high": r.paired_difference.high},
                   **{"pass": next((c.passed for c in r.criteria if c.key == "recall_beats_baseline"), None)})]
    if k:
        cards.append(_card("metric", name="keeper_recall", label="Keeper recall", value=k.substantive_recall.value,
                           interval={"low": k.substantive_recall.low, "high": k.substantive_recall.high}))
    if b:
        cards.append(_card("metric", name="generic_recall", label="Generic review recall",
                           value=b.substantive_recall.value,
                           interval={"low": b.substantive_recall.low, "high": b.substantive_recall.high}))
    cards.append(_card("metric", name="overall", label="Fidelity Test", value="passed" if r.pass_overall else "not passed",
                       **{"pass": r.pass_overall}))
    return res, cards


def get_growth(a: PersonArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import lens as L
    g = L.growth(_lens_id(pid, a.person))
    res = {"health": g.health_state, "explanation": g.explanation_md,
           "periods": [{"period": s.period, "state": s.state, **{k: s.measures.get(k) for k in
                                                                ("prs", "r_plus_rate", "r_plus_hit", "g_novel_rate")}}
                       for s in g.snapshots[-6:]],
           "new_things_noticed": [f.title for f in g.g_examples[:5]]}
    return res, []


def get_usage(a: UsageArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    from keeper.services import usage
    u = usage.usage(a.period or "month", "model")
    return {"period": u.period, "total_usd": u.total.cost_usd, "calls": u.total.calls,
            "rows": [r.model_dump() for r in u.rows], "cap": u.cap.model_dump()}, []


def explain_concept(a: TermArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    terms = get_config().glossary["terms"]
    t = a.term.lower().strip()
    hit = next((x for x in terms if t in (x["key"].lower(), x["label"].lower())), None) or \
        next((x for x in terms if t in x["label"].lower() or t in x["key"].lower().replace("_", " ")), None)
    if hit is None:
        return {"found": False, "known_terms": [x["label"] for x in terms]}, []
    return {"found": True, "label": hit["label"], "short": hit["short"], "long": hit.get("long_md")}, []


# --------------------------------------------------------------------------------------------- action tools
def _action(label: str, path: str, body: dict[str, Any], est: float, *, description: str | None = None,
            href: str | None = None, kind: str) -> dict[str, Any]:
    return _card("action", id=f"act_{kind}", kind=kind, label=label, description=description, method="POST", path=path,
                 body=body, estimate_usd=round(est, 4),
                 expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(), href=href)


def propose_analyze(a: NumberArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    c = _action(f"Analyse PR #{a.number} again", f"{API}/projects/{pid}/pulls/{a.number}/analysis", {},
                estimate("analyze_pr"), href=f"/pr/{a.number}", kind="analyze")
    return {"proposed": c["data"]["label"], "needs_confirmation": True}, [c]


def propose_fix(a: FixArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    c = _action(f"Fix and test {len(a.finding_ids)} finding(s) on #{a.number}",
                f"{API}/projects/{pid}/pulls/{a.number}/fixes", {"finding_ids": a.finding_ids}, estimate("fix_run"),
                description="Runs in a sandbox with the project's tests; nothing is pushed.", href=f"/pr/{a.number}",
                kind="fix")
    return {"proposed": c["data"]["label"], "needs_confirmation": True}, [c]


def propose_handoff(a: NumberArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    res: dict[str, Any] = {"needs_confirmation": True}
    try:
        from keeper.services import pulls
        h = pulls.get_handoff(pid, a.number)
        if h.candidates:
            top = h.candidates[0]
            res["suggested"] = {"login": top.person.login, "why": top.why[:3]}
    except Exception:  # noqa: BLE001
        pass
    c = _action(f"Draft a hand-off note for #{a.number}", f"{API}/projects/{pid}/pulls/{a.number}/handoff", {},
                estimate("handoff"), description="Suggests a reviewer with a different lens and drafts the note.",
                href=f"/pr/{a.number}?tab=handoff", kind="handoff")
    res["proposed"] = c["data"]["label"]
    return res, [c]


def propose_rebuild_lens(a: ReasonArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    lid = _lens_id(pid, None)
    c = _action("Rebuild the lens from all reviews", f"{API}/lenses/{lid}/rebuild", {"reason": a.reason},
                estimate("lens_build"), href="/lens", kind="rebuild_lens")
    return {"proposed": c["data"]["label"], "needs_confirmation": True}, [c]


def propose_fidelity_run(a: Empty, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    n = 30
    try:
        from keeper.services import proof
        runs = proof.list_runs(pid).items
        n = runs[0].prs if runs else n
    except Exception:  # noqa: BLE001
        pass
    c = _action(f"Run the Fidelity Test on {n} held-out PRs", f"{API}/projects/{pid}/fidelity-runs", {},
                estimate("fidelity_per_pr", n), href="/proof", kind="fidelity")
    return {"proposed": c["data"]["label"], "needs_confirmation": True}, [c]


def propose_practice(a: PracticeArgs, ctx: Ctx, pid: str):  # type: ignore[no-untyped-def]
    body: dict[str, Any] = {"kind": "learn"}
    if a.length:
        body["length"] = a.length
    if a.person:
        with session_scope() as db:
            p = project(db, pid)
            pe = db.execute(select(M.Person).where(M.Person.project_id == p.id, M.Person.login == a.person.lstrip("@"))
                            ).scalars().first()
            if pe:
                body["target_person_id"] = pe.id
    c = _action("Start a practice session", f"{API}/projects/{pid}/practice/sessions", body,
                estimate("practice_item", a.length or int(get_config().growth["practice"]["k"])), href="/practice",
                kind="practice")
    return {"proposed": c["data"]["label"], "needs_confirmation": True}, [c]


def _n(a: dict[str, Any]) -> str:
    return f"#{a.get('number')}"


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_queue", "read", "Open pull requests by lane with reasons and attention minutes.", QueueArgs,
         lambda a: "Reading the queue", get_queue),
    Tool("get_pull", "read", "One pull request: summary, lane, findings by lane, signals, fix status.", NumberArgs,
         lambda a: f"Looking at PR {_n(a)}", get_pull),
    Tool("get_finding", "read", "One finding with its evidence and lens items.", FindingArgs,
         lambda a: "Reading a finding", get_finding),
    Tool("search_history", "read", "Search past review comments (keyword search).", SearchArgs,
         lambda a: f"Searching past reviews for “{a.get('query', '')}”", search_history),
    Tool("get_lens", "read", "A person's lens: card, top items, health.", LensArgs,
         lambda a: "Reading the lens", get_lens),
    Tool("get_lens_item", "read", "One lens item with exemplars.", ItemArgs,
         lambda a: "Reading a lens item", get_lens_item),
    Tool("diff_lens_versions", "read", "What changed between two lens versions.", DiffArgs,
         lambda a: "Comparing lens versions", diff_lens_versions),
    Tool("get_proof", "read", "The latest Fidelity Test result: metrics, criteria, falsifiers.", ProofArgs,
         lambda a: "Reading the Proof results", get_proof),
    Tool("get_growth", "read", "A person's growth and lens health over time.", PersonArgs,
         lambda a: "Reading growth history", get_growth),
    Tool("get_usage", "read", "Model spend by model.", UsageArgs, lambda a: "Reading usage", get_usage),
    Tool("explain_concept", "read", "A glossary entry (lanes, lens, residual, Proof…).", TermArgs,
         lambda a: f"Looking up “{a.get('term', '')}”", explain_concept),
    Tool("propose_analyze", "action", "Propose analysing a PR again (the user confirms).", NumberArgs,
         lambda a: f"Preparing to analyse {_n(a)}", propose_analyze),
    Tool("propose_fix", "action", "Propose fixing and testing findings on a PR (the user confirms).", FixArgs,
         lambda a: f"Preparing a fix for {_n(a)}", propose_fix),
    Tool("propose_handoff", "action", "Propose a hand-off to another reviewer (the user confirms).", NumberArgs,
         lambda a: f"Preparing a hand-off for {_n(a)}", propose_handoff),
    Tool("propose_rebuild_lens", "action", "Propose rebuilding the lens (the user confirms).", ReasonArgs,
         lambda a: "Preparing a lens rebuild", propose_rebuild_lens),
    Tool("propose_fidelity_run", "action", "Propose running the Fidelity Test (the user confirms).", Empty,
         lambda a: "Preparing a Proof run", propose_fidelity_run),
    Tool("propose_practice", "action", "Propose a practice session (the user confirms).", PracticeArgs,
         lambda a: "Preparing a practice session", propose_practice),
]}


def schemas() -> list[dict[str, Any]]:
    """OpenAI-style tool definitions."""
    out = []
    for t in TOOLS.values():
        js = t.args.model_json_schema(by_alias=True)
        js.pop("title", None)
        for v in js.get("properties", {}).values():
            v.pop("title", None)
        out.append({"type": "function", "function": {"name": t.name, "description": t.description,
                                                     "parameters": {"type": "object", **js}}})
    return out


_ = current_version

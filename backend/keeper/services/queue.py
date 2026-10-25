"""The queue (FR-Q, FR-TRI): open PRs by lane and attention, the budget summary, refresh and the digest."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config
from keeper.core.errors import Forbidden
from keeper.core.globs import area_of
from keeper.core.types import LANE_ORDER
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.route.attention import naive_minutes
from keeper.services import views as V
from keeper.services.common import (
    confirm,
    estimate,
    job_ref,
    maintainer,
    person_ref,
    prefer_live,
    project,
    provenance,
    require_live,
)


def budget() -> int:
    from keeper.services.settings import override
    v = override("attention_budget_minutes")
    return int(v if v is not None else get_config().ui["editable_settings"]["attention_budget_minutes"]["default"])


def _row(db, p: M.Project, pr: M.Pull, people: dict[str, M.Person]) -> S.QueueRow:  # type: ignore[no-untyped-def]
    a = V.current_analysis(db, p.id, pr)
    au = people.get(pr.author_id or "")
    author = S.AuthorRef(id=au.id if au else None, login=au.login if au else "?", display_name=au.display_name if au else None,
                         association=pr.author_association,
                         first_time=pr.author_association in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"))
    files = [f.filename for f in db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id)).scalars()]
    areas = sorted({area_of(f, 2) for f in files})
    if a is None:
        return S.QueueRow(number=pr.number, title=pr.title, author=author, lane="unknown", summary=None,
                          reasons=[S.Reason(kind="pending", label="Not sorted yet")], signals=[], attention_minutes=0,
                          counts=S.LaneCounts(), status="waiting", areas=areas, files=files, labels=pr.labels or [],
                          updated_at=pr.updated_at, created_at=pr.created_at, head_sha=pr.head_sha,
                          provenance=provenance("live", None))
    rfs = db.execute(select(M.RoutedFindingRow).where(M.RoutedFindingRow.analysis_id == a.id)).scalars().all()
    c = Counter(r.lane for r in rfs if r.user_state != "dismissed")
    fixes = db.execute(select(M.FixRun).where(M.FixRun.project_id == p.id, M.FixRun.pr_number == pr.number)).scalars().all()
    fx = prefer_live(fixes)
    ho = db.execute(select(M.Handoff).where(M.Handoff.analysis_id == a.id)).scalars().first()
    hp = people.get(ho.target_person_id) if ho and ho.target_person_id else None
    slop = (a.stats or {}).get("slop", {})
    status = "fixed_and_tested" if fx and fx.status == "passed" else (
        "draft_ready" if db.execute(select(M.ReviewDraft.id).where(M.ReviewDraft.analysis_id == a.id)).first()
        else "analysed")
    return S.QueueRow(
        number=pr.number, title=pr.title, author=author, lane=V.effective_lane(db, p.id, a), summary=a.summary,
        reasons=[S.Reason(**r) for r in (a.reasons or [])][:6], signals=V.signal_refs(a),
        attention_minutes=a.attention_minutes,
        counts=S.LaneCounts(edge=c.get("edge", 0), blind_spot=c.get("blind_spot", 0), shared=c.get("shared", 0),
                            baseline_only=c.get("baseline_only", 0)),
        slop=S.SlopInfo(score=float(slop.get("score", 0)), label="Looks auto-generated" if slop.get("is_slop") else None,
                        evidence=slop.get("evidence", [])) if slop else None,
        fix=S.FixRef(status=fx.status, run_id=fx.id) if fx else None,
        handoff=S.HandoffRef(person_id=hp.id, login=hp.login, display_name=hp.display_name) if hp else None,
        status=status, areas=areas, files=files, labels=pr.labels or [], updated_at=pr.updated_at,
        created_at=pr.created_at, head_sha=pr.head_sha, analysis_id=a.id, provenance=V.analysis_provenance(db, a))


def get_queue(pid: str, *, lane: str | None = None, sort: str = "attention", q: str | None = None) -> S.QueueResponse:
    with session_scope() as db:
        p = project(db, pid)
        people = {x.id: x for x in db.execute(select(M.Person).where(M.Person.project_id == p.id)).scalars()}
        pulls = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.state == "open")).scalars().all()
        rows = [_row(db, p, pr, people) for pr in pulls]
        by_lane = Counter(r.lane for r in rows if r.status != "waiting")
        att: Counter[str] = Counter()
        for r in rows:
            att[r.lane] += r.attention_minutes
        total = sum(att.values())
        b = budget()
        naive = naive_minutes([pr.additions + pr.deletions for pr in pulls], get_config().routing)
        unknown = sorted([r for r in rows if r.lane == "unknown"], key=lambda r: -r.attention_minutes)
        summary = S.QueueSummary(by_lane=S.ByLane(**{k: by_lane.get(k, 0) for k in LANE_ORDER}),
                                 attention_by_lane=S.AttentionByLane(**{k: att.get(k, 0) for k in LANE_ORDER}),
                                 attention_minutes_total=total, budget_minutes=b, over_budget=total > b,
                                 need_count=by_lane.get("edge", 0) + by_lane.get("blind_spot", 0), total=len(rows),
                                 naive_minutes=naive, handoff_suggestion=unknown[0].number if total > b and unknown else None)
        if lane:
            rows = [r for r in rows if r.lane == lane]
        if q:
            ql = q.lower().lstrip("#")
            rows = [r for r in rows if ql in r.title.lower() or ql == str(r.number) or ql in r.author.login.lower()
                    or any(ql in f.lower() for f in r.files)]
        if sort == "updated":
            rows.sort(key=lambda r: r.updated_at or r.created_at, reverse=True)
        elif sort == "number":
            rows.sort(key=lambda r: r.number)
        else:
            rows.sort(key=lambda r: (LANE_ORDER.index(r.lane), -r.attention_minutes, r.created_at))
        snaps = [r.provenance for r in rows]
        prov = snaps[0] if snaps else provenance("live", None)
        return S.QueueResponse(items=rows, summary=summary, provenance=prov, maintainer=person_ref(maintainer(db, p)))


def refresh(pid: str, body: S.QueueRefreshRequest, ctx: Ctx) -> S.JobAccepted:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer can refresh the queue.")
    require_live()
    with session_scope() as db:
        p = project(db, pid)
        nums = body.numbers or [pr.number for pr in db.execute(select(M.Pull).where(
            M.Pull.project_id == p.id, M.Pull.state == "open")).scalars()]
    confirm("triage", {"pid": pid, "numbers": sorted(nums)}, estimate("analyze_pr", len(nums)), body.confirm_token,
            f"Analyse {len(nums)} pull requests")
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("triage", {"project_id": pid, "numbers": nums}, key=f"triage:{pid}")
    return job_ref(jid, "triage", existing)


def digest(pid: str) -> S.QueueDigest:
    q = get_queue(pid)
    s = q.summary
    m = q.maintainer
    name = (m.display_name or m.login) if m else ""
    lines = [f"**{s.need_count} of {s.total}** open pull requests need {name}'s eye (about {s.attention_minutes_total} "
             f"of {s.budget_minutes} minutes)."]
    for lane, label in (("edge", "Needs your eye"), ("blind_spot", "Worth a second look"),
                        ("unknown", "Needs another reviewer"), ("shared", "Handled for you")):
        rows = [r for r in q.items if r.lane == lane]
        if rows:
            lines.append(f"- {label}: " + ", ".join(f"[[pull:{r.number}]]" for r in rows))
    lines.append(f"\nReviewing everything in full would take about {s.naive_minutes} minutes.")
    cards = [S.Card(type="pull", data={"number": r.number, "title": r.title, "lane": r.lane,
                                       "reason": r.reasons[0].label if r.reasons else ""}) for r in q.items]
    return S.QueueDigest(markdown="\n".join(lines), cards=cards)

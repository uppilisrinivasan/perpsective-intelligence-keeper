"""Practice: the Growth Test (FR-GRO): before / learn / after sessions on held-out PRs, scored against the target."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select

from keeper.analysis.context import pr_files
from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config, get_settings
from keeper.core.errors import Conflict, NotFound
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.growth import forms as FM
from keeper.growth import practice as PR
from keeper.ids import new_id
from keeper.services.common import (
    current_version,
    is_simulated,
    lens_of,
    maintainer,
    person_ref,
    project,
    require_live,
)

_banks: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
MEASURED = ("before", "after")


def learner_key(learner: str | None, ctx: Ctx) -> str:
    """"me" is the guest key (a cookie); a person is named by login or id and keyed by login."""
    if learner in (None, "", "me"):
        return ctx.guest_key
    pe = _learner_person(learner)
    return f"person:{pe.login if pe else learner}"


def _learner_person(learner: str | None) -> M.Person | None:
    if learner in (None, "", "me"):
        return None
    with session_scope() as db:
        pe = db.get(M.Person, learner) or db.execute(select(M.Person).where(M.Person.login == learner)).scalars().first()
        if pe is not None:
            db.expunge(pe)
        return pe


def _target(db, p: M.Project, person_id: str | None) -> M.Person:  # type: ignore[no-untyped-def]
    if person_id:
        pe = db.get(M.Person, person_id)
        if pe is None or pe.project_id != p.id:
            raise NotFound("Person not found.")
        return pe
    return maintainer(db, p)


def _bank(db, p: M.Project, target: M.Person, lv: M.LensVersion | None) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    key = (p.id, target.id, lv.id if lv else None)
    if key not in _banks:
        _banks[key] = PR.item_bank(db, p, target, lv)
    return _banks[key]


def _forms(bank: list[dict[str, Any]], lkey: str) -> tuple[list[int], list[int]]:
    g = get_config().growth["practice"]
    seed = int(hashlib.sha256(lkey.encode()).hexdigest()[:8], 16)
    a, b = FM.parallel_forms(bank, set(), int(g["k"]), dict(g["strata"]), seed, dict(g["balance"]))
    return [i["pr"] for i in a], [i["pr"] for i in b]


def _sessions(db, p: M.Project, lkey: str) -> list[M.PracticeSession]:  # type: ignore[no-untyped-def]
    return db.execute(select(M.PracticeSession).where(M.PracticeSession.project_id == p.id,
                                                      M.PracticeSession.learner_key == lkey)
                      .order_by(M.PracticeSession.created_at)).scalars().all()


def _growth(sessions: list[M.PracticeSession]) -> dict[str, Any] | None:
    done = [s for s in sessions if s.status == "complete"]
    before = next((s for s in reversed(done) if s.kind == "before"), None)
    after = next((s for s in reversed(done) if s.kind == "after"), None)
    if before is None:
        return None
    out: dict[str, Any] = {"before": before.result}
    if after is not None:
        out["after"] = after.result
        for k in ("recall", "costly_recall"):
            b, a = (before.result or {}).get(k), (after.result or {}).get(k)
            out[f"delta_{k}"] = round(a - b, 3) if a is not None and b is not None else None
        out["noise_delta"] = (after.result or {}).get("noise", 0) - (before.result or {}).get("noise", 0)
    return out


def overview(pid: str, learner: str, ctx: Ctx) -> S.PracticeOverview:
    with session_scope() as db:
        p = project(db, pid)
        lkey = learner_key(learner, ctx)
        target = maintainer(db, p)
        lens = lens_of(db, p, target.id)
        ss = _sessions(db, p, lkey)
        done = {s.kind for s in ss if s.status == "complete"}
        nxt = "before" if "before" not in done else "learn" if "learn" not in done else \
            "after" if "after" not in done else None
        lp = _learner_person(learner)
        bank = _bank(db, p, target, current_version(db, lens))
        return S.PracticeOverview(
            learner_key=lkey, learner=person_ref(lp), target=person_ref(target),
            sessions=[S.PracticeSessionRef(id=s.id, kind=s.kind, status=s.status, created_at=s.created_at,
                                           items=len(s.item_pr_numbers or []), recall=(s.result or {}).get("recall"),
                                           origin="snapshot" if s.origin == "snapshot" else "live") for s in ss],
            growth=_growth(ss), next_kind=nxt, bank_size=len(bank) if bank else 0,
            lens_shared=bool(lens is None or lens.shared_in_project), scoring_available=get_settings().live)


def _item_status(db, s: M.PracticeSession, n: int) -> str:  # type: ignore[no-untyped-def]
    a = db.execute(select(M.PracticeAnswer).where(M.PracticeAnswer.session_id == s.id, M.PracticeAnswer.pr_number == n)
                   .order_by(M.PracticeAnswer.attempt.desc())).scalars().first()
    if a is None:
        return "pending"
    return "done" if (a.feedback or {}).get("status") in ("revealed", "recorded") else "attempted"


def _session_out(db, s: M.PracticeSession) -> S.PracticeSessionOut:  # type: ignore[no-untyped-def]
    return S.PracticeSessionOut(id=s.id, kind=s.kind, items=[S.PracticeItemRef(pr_number=n, status=_item_status(db, s, n))
                                                            for n in s.item_pr_numbers or []],
                                current_index=s.current_index, status=s.status,
                                target=person_ref(db.get(M.Person, s.target_person_id)),
                                origin="snapshot" if s.origin == "snapshot" else "live",
                                result=s.result or None)


def start_session(pid: str, body: S.PracticeStart, ctx: Ctx) -> S.PracticeSessionOut:
    g = get_config().growth["practice"]
    with session_scope() as db:
        p = project(db, pid)
        target = _target(db, p, body.target_person_id)
        lens = lens_of(db, p, target.id)
        if lens is not None and not lens.shared_in_project and ctx.role != "maintainer":
            raise Conflict("This lens isn't shared for practice.")
        lv = current_version(db, lens)
        lkey = learner_key(body.learner, ctx)
        bank = _bank(db, p, target, lv)
        if not bank:
            raise Conflict("There aren't enough held-out reviewed PRs to practise on.")
        before, after = _forms(bank, lkey)
        used = set(before) | set(after)
        prev = _sessions(db, p, lkey)
        seen = {n for s in prev if s.kind in ("learn", "taste") for n in s.item_pr_numbers or []}
        if body.kind == "before":
            items = before
        elif body.kind == "after":
            if not any(s.kind == "before" and s.status == "complete" for s in prev):
                raise Conflict("Do the before check first, so the after check has something to compare with.")
            items = after
        else:
            buckets = set(g["taste_buckets"]) if body.kind == "taste" else {"easy", "medium", "hard"}
            pool = [i for i in sorted(bank, key=lambda i: i["difficulty"]) if i["pr"] not in used and
                    i["bucket"] in buckets]
            fresh = [i for i in pool if i["pr"] not in seen] or pool
            n = body.length or (1 if body.kind == "taste" else int(g["k"]))
            items = [i["pr"] for i in fresh[:n]]
        if not items:
            raise Conflict("No practice PRs are left for this kind of session.")
        s = PR.new_session(db, p, lkey, target, body.kind, items, lv)
        return _session_out(db, s)


def _session(db, sid: str, ctx: Ctx) -> M.PracticeSession:  # type: ignore[no-untyped-def]
    s = db.get(M.PracticeSession, sid)
    if s is None:
        raise NotFound("Practice session not found.")
    return s


def get_session(sid: str, ctx: Ctx) -> S.PracticeSessionOut:
    with session_scope() as db:
        return _session_out(db, _session(db, sid, ctx))


def _pr_at(db, s: M.PracticeSession, idx: int) -> int:  # type: ignore[no-untyped-def]
    items = s.item_pr_numbers or []
    if idx < 0 or idx >= len(items):
        raise NotFound("No such practice item.")
    return int(items[idx])


def _answers(db, s: M.PracticeSession, n: int) -> list[M.PracticeAnswer]:  # type: ignore[no-untyped-def]
    return db.execute(select(M.PracticeAnswer).where(M.PracticeAnswer.session_id == s.id,
                                                     M.PracticeAnswer.pr_number == n)
                      .order_by(M.PracticeAnswer.attempt)).scalars().all()


def get_item(sid: str, idx: int, ctx: Ctx) -> S.PracticeItemOut:
    with session_scope() as db:
        s = _session(db, sid, ctx)
        n = _pr_at(db, s, idx)
        p = db.get(M.Project, s.project_id)
        pr = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.number == n)).scalars().one()
        target = db.get(M.Person, s.target_person_id)
        hs = PR.target_findings(db, p, target, n)
        head = (hs[0].head_sha if hs else None) or pr.head_sha
        files = pr_files(db, p, pr, head)
        ans = _answers(db, s, n)
        return S.PracticeItemOut(pr_number=n, title=pr.title, body_md=pr.body or "",
                                 files=[S.PullFileInfo(filename=f.path, status=f.status, additions=f.additions,
                                                       deletions=f.deletions, binary=f.binary) for f in files],
                                 diff=[S.DiffFile(filename=f.path, status=f.status, patch=f.patch, binary=f.binary)
                                       for f in files],
                                 hint_available=s.kind in ("learn", "taste"), attempt=len(ans) + 1, index=idx,
                                 total=len(s.item_pr_numbers or []), saved_notes=list(ans[-1].notes) if ans else [])


def _feedback(s: M.PracticeSession, a: M.PracticeAnswer, *, reveal_measured: bool = False) -> S.PracticeFeedback:
    fb = a.feedback or {}
    hide = s.kind in MEASURED and not reveal_measured
    return S.PracticeFeedback(attempt=a.attempt, status=fb.get("status", "recorded"),
                              hints=[] if hide else list(a.hints or []), reveal=None if hide else fb.get("reveal"),
                              measures={} if hide else fb.get("measures", {}),
                              scoring_simulated=bool(fb.get("simulated")))


async def submit_answer(sid: str, idx: int, body: S.PracticeAnswerRequest, ctx: Ctx) -> S.PracticeFeedback:
    require_live()
    from keeper.llm.gateway import get_gateway
    gw = get_gateway()
    # an empty answer ("I don't see anything") is valid and scores zero recall
    notes = [n.model_dump() for n in body.notes if n.text.strip()]
    with session_scope() as db:
        s = _session(db, sid, ctx)
        if s.status == "complete":
            raise Conflict("This session is finished.")
        n = _pr_at(db, s, idx)
        p = db.get(M.Project, s.project_id)
        target = db.get(M.Person, s.target_person_id)
        lv = db.get(M.LensVersion, s.lens_version_id) if s.lens_version_id else None
        prev = _answers(db, s, n)
        if prev and (prev[-1].feedback or {}).get("status") in ("revealed", "recorded"):
            raise Conflict("This PR is already done; go to the next one.")
        aid = new_id("pra")
        scored = await PR.score(db, p, target, n, notes, aid, lv, gateway=gw)
        attempt = len(prev) + 1
        hints: list[dict[str, Any]] = []
        if s.kind in MEASURED:
            status = "recorded"
        elif attempt == 1 and scored["costly_misses"]:
            hints = await PR.hints(db, p, target, n, scored, notes, lv, gateway=gw)
            status = "hint" if hints else "revealed"
        else:
            status = "revealed"
        reveal = PR.reveal(db, p, target, n, scored, notes, lv) if status in ("revealed", "recorded") else None
        measures = {k: scored[k] for k in ("recall", "costly_recall", "n_target", "matched")} | {
            "caught": len(scored["caught"]), "missed": len(scored["missed"]), "own_eye": len(scored["own_eye"]),
            "noise": len(scored["noise"])}
        models = [scored["model"].get("model")] if scored.get("model") else []
        a = M.PracticeAnswer(id=aid, session_id=s.id, pr_number=n, attempt=attempt, notes=notes, hints=hints,
                             feedback={"status": status, "scored": scored, "reveal": reveal, "measures": measures,
                                       "simulated": is_simulated(models) or gw.fake},
                             status="scored")
        db.add(a)
        if status in ("revealed", "recorded"):
            s.current_index = min(idx + 1, len(s.item_pr_numbers or []))
        db.flush()
        return _feedback(s, a)


def get_feedback(sid: str, idx: int, ctx: Ctx) -> S.PracticeFeedback:
    with session_scope() as db:
        s = _session(db, sid, ctx)
        n = _pr_at(db, s, idx)
        ans = _answers(db, s, n)
        if not ans:
            raise NotFound("No answer yet.")
        return _feedback(s, ans[-1], reveal_measured=s.status == "complete")


def complete(sid: str, ctx: Ctx) -> S.PracticeResult:
    with session_scope() as db:
        s = _session(db, sid, ctx)
        last = []
        for n in s.item_pr_numbers or []:
            ans = _answers(db, s, n)
            if ans:
                last.append(ans[-1].feedback or {})
        if not last:
            raise Conflict("Answer at least one PR before finishing.")
        res = PR.session_result(last, s.kind)
        s.result = res
        s.status = "complete"
        db.flush()
        p = db.get(M.Project, s.project_id)
        g = _growth(_sessions(db, p, s.learner_key))
        out = dict(res)
        if s.kind == "after" and g:
            out["growth"] = g
        return S.PracticeResult(result=out)

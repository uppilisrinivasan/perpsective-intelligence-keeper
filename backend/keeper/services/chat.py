"""Ask: chat threads, suggested prompts built from data, and saved examples for no-key mode."""

from __future__ import annotations

import json

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config, get_settings
from keeper.core.errors import NotFound
from keeper.db import models as M
from keeper.db import repo as R
from keeper.db.session import session_scope
from keeper.ids import new_id
from keeper.services.common import current_version, lens_of, maintainer, name_of, project


def _thread_out(t: M.ChatThread) -> S.ChatThreadOut:
    return S.ChatThreadOut(id=t.id, title=t.title, context=t.context or {}, updated_at=t.updated_at,
                           origin="snapshot" if t.origin == "snapshot" else "live")


def list_threads(context: str | None) -> S.ChatThreadList:
    with session_scope() as db:
        rows = db.execute(select(M.ChatThread).order_by(M.ChatThread.updated_at.desc())).scalars().all()
        if context:
            rows = [t for t in rows if (t.context or {}).get("screen") == context]
        return S.ChatThreadList(items=[_thread_out(t) for t in rows])


def create_thread(body: S.ChatThreadCreate, ctx: Ctx) -> S.ChatThreadDetail:
    with session_scope() as db:
        p = project(db, (body.context or {}).get("project_id"))
        t = M.ChatThread(id=new_id("thr"), title="New chat", role=ctx.role, project_id=p.id, context=body.context or {})
        db.add(t)
        db.flush()
        return S.ChatThreadDetail(**_thread_out(t).model_dump(), messages=[])


def _messages(db, tid: str) -> list[S.ChatMessageOut]:  # type: ignore[no-untyped-def]
    out = []
    for m in db.execute(select(M.ChatMessage).where(M.ChatMessage.thread_id == tid, M.ChatMessage.role.in_(
            ["user", "assistant"])).order_by(M.ChatMessage.created_at)).scalars():
        tr = list(m.tool_trace or [])
        model = next((t.get("model") for t in tr if t.get("model")), None)
        cost = next((t.get("cost_usd") for t in tr if t.get("cost_usd") is not None), None)
        out.append(S.ChatMessageOut(id=m.id, role=m.role, content_md=m.content or "",
                                    cards=[S.Card(**c) for c in m.cards or []],
                                    tool_trace=[t for t in tr if t.get("name")], created_at=m.created_at,
                                    model=model, cost_usd=cost))
    return out


def get_thread(tid: str) -> S.ChatThreadDetail:
    with session_scope() as db:
        t = db.get(M.ChatThread, tid)
        if t is None:
            raise NotFound("Chat not found.")
        return S.ChatThreadDetail(**_thread_out(t).model_dump(), messages=_messages(db, tid))


def rename_thread(tid: str, title: str) -> S.ChatThreadDetail:
    with session_scope() as db:
        t = db.get(M.ChatThread, tid)
        if t is None:
            raise NotFound("Chat not found.")
        t.title = title.strip()[:80] or t.title
    return get_thread(tid)


def delete_thread(tid: str) -> None:
    with session_scope() as db:
        t = db.get(M.ChatThread, tid)
        if t is None:
            raise NotFound("Chat not found.")
        db.delete(t)


def ensure_thread(tid: str) -> None:
    with session_scope() as db:
        if db.get(M.ChatThread, tid) is None:
            raise NotFound("Chat not found.")


def suggestions(context: str | None, number: int | None) -> S.SuggestionList:
    """Templates from config/ui.yaml; slot values from the current data. A template whose slot has no value is
    skipped rather than shown with a gap."""
    from keeper.services import queue
    tpl = get_config().ui["assistant"]["suggestions"]
    screen = context if context in tpl else "default"
    values: dict[str, str] = {}
    with session_scope() as db:
        try:
            p = project(db, None)
        except NotFound:
            return S.SuggestionList(items=[S.Suggestion(text=t) for t in tpl["default"]
                                           if "{" not in t])
        m = maintainer(db, p)
        values["maintainer"] = name_of(m)
        lv = current_version(db, lens_of(db, p, m.id))
        if lv and lv.version > 1:
            values["prev_version"] = str(lv.version - 1)
        pid = p.id
    if screen == "queue":
        q = queue.get_queue(pid, lane="unknown")
        if q.items:
            values["top_unknown"] = str(q.items[0].number)
    if screen == "pr" and number:
        from keeper.services import pulls
        try:
            an = pulls.get_analysis(pid, number, Ctx(role="maintainer", request_id="sugg", guest_key=""))
            edge = next((f for f in an.findings if f.lane == "edge"), None)
            if edge:
                values["top_edge_title"] = edge.title
        except NotFound:
            pass
    out = []
    for t in tpl[screen]:
        try:
            out.append(S.Suggestion(text=t.format(**values), context={"screen": screen, "number": number}
                                    if number else {"screen": screen}))
        except (KeyError, IndexError):
            continue
    if not out:
        out = [S.Suggestion(text=t) for t in tpl["default"]]
    return S.SuggestionList(items=out)


def examples() -> S.ChatExampleList:
    s = get_settings()
    with session_scope() as db:
        try:
            p = project(db, None)
        except NotFound:
            return S.ChatExampleList(items=[])
        snap = R.get_state(db, "snapshot") or {}
        f = s.data_dir / "snapshots" / p.id / "chat_examples.jsonl"
    if not f.exists():
        return S.ChatExampleList(items=[], simulated=bool(snap.get("simulated")))
    items = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            items.append(S.ChatExample(id=d["id"], question=d["question"], answer_md=d["answer_md"],
                                       cards=[S.Card(**c) for c in d.get("cards", [])],
                                       tool_trace=d.get("tool_trace", [])))
    return S.ChatExampleList(items=items, simulated=bool(snap.get("simulated")))

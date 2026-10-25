"""Jobs: long work with persisted state and streamed events (docs/04-architecture/04-jobs-and-streaming.md).

Jobs run in this process on an asyncio worker pool. Events are rows in job_events (the SSE `id`), so a browser
refresh resumes without loss; live subscribers also get them from an in-process queue.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from keeper.config import get_settings
from keeper.core.errors import KeeperError
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.ids import new_id
from keeper.logging import get_logger

log = get_logger("keeper.jobs")
Handler = Callable[["JobContext"], Awaitable[dict[str, Any]]]
_handlers: dict[str, Handler] = {}
_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
_cancel: set[str] = set()
TERMINAL = ("job.completed", "job.failed", "job.cancelled")
THROTTLED = ("fix.test.output", "job.log")


def handler(kind: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _handlers[kind] = fn
        return fn
    return deco


def _now() -> datetime:
    return datetime.now(UTC)


def publish(job_id: str, ev: dict[str, Any]) -> None:
    for q in list(_subscribers.get(job_id, [])):
        q.put_nowait(ev)


def subscribe(job_id: str) -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[job_id].append(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
    if q in _subscribers.get(job_id, []):
        _subscribers[job_id].remove(q)


_seq = {"next": None}
_seq_lock = __import__("threading").Lock()


def _next_event_id() -> int:
    with _seq_lock:
        if _seq["next"] is None:
            with session_scope() as db:
                _seq["next"] = int(db.execute(select(func.coalesce(func.max(M.JobEvent.id), 0))).scalar_one()) + 1
        n = _seq["next"]
        _seq["next"] = n + 1
        return n


def record_event(job_id: str, type_: str, data: dict[str, Any]) -> dict[str, Any]:
    """Publish now (live subscribers) and persist write-behind with the same ID (replay after reconnects)."""
    from keeper.db import sidecar
    at = _now()
    payload = {"job_id": job_id, "at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), **data}
    eid = _next_event_id()
    sidecar.add(M.JobEvent(id=eid, job_id=job_id, type=type_, data=payload, at=at))
    ev = {"id": eid, "event": type_, "data": payload}
    publish(job_id, ev)
    return ev


def _update_job(job_id: str, **fields: Any) -> None:
    from keeper.db import sidecar

    def op(db: Any) -> None:
        j = db.get(M.Job, job_id)
        if j:
            for k, v in fields.items():
                setattr(j, k, v)
    sidecar.submit(op)


class JobContext:
    """What a running job sees: its id and params, events, progress, cost and cancellation."""

    def __init__(self, job_id: str, kind: str, params: dict[str, Any]):
        self.id = job_id
        self.kind = kind
        self.params = params
        self.cost_usd = 0.0
        self._last: dict[str, float] = {}
        self._cost_at = 0.0

    async def event(self, type_: str, data: dict[str, Any] | None = None) -> None:
        if type_ in THROTTLED:
            now = time.time()
            if now - self._last.get(type_, 0) < 0.25:
                return
            self._last[type_] = now
        record_event(self.id, type_, data or {})
        await self._update_cost()

    async def step(self, label: str, index: int, total: int, step: str | None = None) -> None:
        _update_job(self.id, step=label, progress=round(max(0.0, (index - 1) / max(1, total)), 3))
        record_event(self.id, "job.step", {"step": step or label, "label": label, "index": index, "total": total})

    async def progress(self, done: int, total: int, stage: str | None = None) -> None:
        p = round(done / max(1, total), 3)
        _update_job(self.id, progress=p)
        now = time.time()
        if now - self._last.get("progress", 0) > 0.5 or done == total:
            self._last["progress"] = now
            record_event(self.id, "job.progress", {"progress": p, "done": done, "total": total, "stage": stage})
        await self._update_cost()

    async def warn(self, code: str, message: str) -> None:
        record_event(self.id, "job.warning", {"code": code, "message": message})

    async def log(self, message: str, level: str = "info") -> None:
        await self.event("job.log", {"level": level, "message": message})

    async def cancelled(self) -> bool:
        return self.id in _cancel

    async def _update_cost(self) -> None:
        now = time.time()
        if now - self._cost_at < 2:
            return
        self._cost_at = now
        from keeper.llm.meter import _recent
        mine = [r for r in _recent if r.get("job_id") == self.id]
        self.cost_usd = float(sum(r.get("cost_usd", 0.0) for r in mine))
        calls = len(mine)
        _update_job(self.id, cost_usd=self.cost_usd)
        record_event(self.id, "job.cost", {"cost_usd": round(self.cost_usd, 4), "calls": int(calls)})


class Runner:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.workers: list[asyncio.Task[None]] = []
        self.running: dict[str, asyncio.Task[Any]] = {}

    def start(self) -> None:
        n = max(1, get_settings().JOB_WORKERS)
        loop = asyncio.get_event_loop()
        self.workers = [loop.create_task(self._worker(i)) for i in range(n)]

    async def stop(self) -> None:
        for w in self.workers:
            w.cancel()
        for t in self.running.values():
            t.cancel()

    def submit(self, kind: str, params: dict[str, Any], *, key: str | None = None) -> tuple[str, bool]:
        """Queue a job; a job of the same kind and key that is still running is returned instead (dedup)."""
        with session_scope() as db:
            if key:
                existing = db.execute(select(M.Job).where(M.Job.kind == kind, M.Job.key == key,
                                                          M.Job.status.in_(["queued", "running"]))).scalars().first()
                if existing:
                    return existing.id, True
            jid = new_id("job")
            db.add(M.Job(id=jid, kind=kind, key=key, status="queued", params=params,
                         runner=get_settings().JOB_RUNNER if kind in ("learn", "recalibrate", "fidelity") else "local"))
        record_event(jid, "job.queued", {"kind": kind, "params": params})
        self.queue.put_nowait(jid)
        return jid, False

    async def run_inline(self, kind: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Run a job to completion in the caller's task (CLI, snapshot generation, tests)."""
        jid, _ = self.submit_record(kind, params)
        await self._execute(jid)
        with session_scope() as db:
            j = db.get(M.Job, jid)
            return jid, dict(j.result or {}) if j.status == "succeeded" else {"error": j.error}

    def submit_record(self, kind: str, params: dict[str, Any]) -> tuple[str, bool]:
        with session_scope() as db:
            jid = new_id("job")
            db.add(M.Job(id=jid, kind=kind, status="queued", params=params))
        record_event(jid, "job.queued", {"kind": kind, "params": params})
        return jid, False

    async def _worker(self, i: int) -> None:
        while True:
            jid = await self.queue.get()
            try:
                await self._execute(jid)
            except Exception:  # noqa: BLE001
                log.exception("job worker crashed on %s", jid)

    async def _execute(self, jid: str) -> None:
        with session_scope() as db:
            j = db.get(M.Job, jid)
            if j is None or j.status not in ("queued",):
                return
            kind, params = j.kind, dict(j.params or {})
            j.status, j.started_at = "running", _now()
        record_event(jid, "job.started", {"kind": kind, "runner": "local"})
        ctx = JobContext(jid, kind, params)
        fn = _handlers.get(kind)
        try:
            if fn is None:
                raise KeeperError(f"No handler for job kind {kind!r}")
            task = asyncio.current_task()
            if task:
                self.running[jid] = task
            result = await fn(ctx)
            if jid in _cancel:
                raise asyncio.CancelledError
            ctx._cost_at = 0
            await ctx._update_cost()
            from keeper.db import sidecar
            sidecar.flush(30)
            with session_scope() as db:
                j = db.get(M.Job, jid)
                j.status, j.result, j.finished_at, j.progress, j.cost_usd = "succeeded", result or {}, _now(), 1.0, \
                    ctx.cost_usd
            record_event(jid, "job.completed", {"result": result or {}})
        except asyncio.CancelledError:
            with session_scope() as db:
                j = db.get(M.Job, jid)
                j.status, j.finished_at = "cancelled", _now()
            record_event(jid, "job.cancelled", {})
        except KeeperError as e:
            self._fail(jid, {"code": e.code, "message": e.message, "details": e.details})
        except Exception as e:  # noqa: BLE001
            log.error("job %s failed: %s\n%s", jid, e, traceback.format_exc())
            self._fail(jid, {"code": "error", "message": f"Something went wrong: {type(e).__name__}: {str(e)[:300]}",
                             "details": {}})
        finally:
            self.running.pop(jid, None)
            _cancel.discard(jid)

    @staticmethod
    def _fail(jid: str, err: dict[str, Any]) -> None:
        with session_scope() as db:
            j = db.get(M.Job, jid)
            j.status, j.error, j.finished_at = "failed", err, _now()
        record_event(jid, "job.failed", {"error": err})

    def cancel(self, jid: str) -> None:
        _cancel.add(jid)
        with session_scope() as db:
            j = db.get(M.Job, jid)
            if j and j.status == "queued":
                j.status, j.finished_at = "cancelled", _now()
                record_event(jid, "job.cancelled", {})


def mark_interrupted() -> int:
    """On startup: jobs that were running when the process stopped are `interrupted` (FR-JOB-3)."""
    n = 0
    with session_scope() as db:
        for j in db.execute(select(M.Job).where(M.Job.status.in_(["running", "queued"]))).scalars():
            j.status, j.finished_at = "interrupted", _now()
            n += 1
    return n


_runner: Runner | None = None


def get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner()
    return _runner

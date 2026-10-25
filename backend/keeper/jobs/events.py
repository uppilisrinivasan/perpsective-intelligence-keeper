"""The SSE stream for a job: persisted events after Last-Event-ID, then live ones, with heartbeats; it closes
after the terminal event."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select

from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.jobs.runner import TERMINAL, subscribe, unsubscribe


async def stream(job_id: str, after: int, request: Any) -> AsyncIterator[dict[str, Any]]:
    q = subscribe(job_id)
    try:
        last = after
        with session_scope() as db:
            rows = db.execute(select(M.JobEvent).where(M.JobEvent.job_id == job_id, M.JobEvent.id > after)
                              .order_by(M.JobEvent.id)).scalars().all()
            past = [(r.id, r.type, r.data) for r in rows]
            status = db.get(M.Job, job_id).status
        for eid, typ, data in past:
            last = eid
            yield {"id": str(eid), "event": typ, "data": json.dumps(data)}
            if typ in TERMINAL:
                return
        if status in ("succeeded", "failed", "cancelled", "interrupted"):
            return
        while True:
            if request is not None and await request.is_disconnected():
                return
            try:
                ev = await asyncio.wait_for(q.get(), timeout=15)
            except TimeoutError:
                yield {"comment": "heartbeat"}
                continue
            if ev["id"] <= last:
                continue
            last = ev["id"]
            yield {"id": str(ev["id"]), "event": ev["event"], "data": json.dumps(ev["data"])}
            if ev["event"] in TERMINAL:
                return
    finally:
        unsubscribe(job_id, q)

"""GET /jobs, /jobs/{id}, log, cancel, resume."""

from __future__ import annotations

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.config import get_settings
from keeper.core.errors import Conflict, NotFound
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.jobs.runner import get_runner
from keeper.services.common import job_ref


def _out(j: M.Job) -> S.JobOut:
    return S.JobOut(id=j.id, kind=j.kind, status=j.status, params=j.params or {}, progress=j.progress, step=j.step,
                    result=j.result or {}, error=j.error, cost_usd=round(j.cost_usd or 0, 4), created_at=j.created_at,
                    started_at=j.started_at, finished_at=j.finished_at, events_url=f"/api/v1/jobs/{j.id}/events")


def list_jobs(kind: str | None, status: str | None, limit: int) -> S.JobList:
    with session_scope() as db:
        q = select(M.Job).order_by(M.Job.created_at.desc()).limit(max(1, min(limit, 100)))
        if kind:
            q = q.where(M.Job.kind == kind)
        if status:
            q = q.where(M.Job.status == status)
        return S.JobList(items=[_out(j) for j in db.execute(q).scalars()])


def get_job(job_id: str) -> S.JobOut:
    with session_scope() as db:
        j = db.get(M.Job, job_id)
        if j is None:
            raise NotFound("Job not found.")
        return _out(j)


def job_log(job_id: str) -> str:
    get_job(job_id)
    with session_scope() as db:
        evs = db.execute(select(M.JobEvent).where(M.JobEvent.job_id == job_id).order_by(M.JobEvent.id)).scalars().all()
        return "\n".join(f"{e.at.isoformat()} {e.type} {e.data}" for e in evs) + "\n"


def cancel(job_id: str) -> S.JobOut:
    get_job(job_id)
    get_runner().cancel(job_id)
    return get_job(job_id)


def resume(job_id: str) -> S.JobAccepted:
    j = get_job(job_id)
    if j.status not in ("interrupted", "failed"):
        raise Conflict("Only interrupted or failed jobs can be resumed.")
    jid, existing = get_runner().submit(j.kind, j.params)
    return job_ref(jid, j.kind, existing)


_ = get_settings

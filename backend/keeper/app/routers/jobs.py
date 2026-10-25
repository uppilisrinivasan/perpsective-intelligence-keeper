from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response
from sse_starlette.sse import EventSourceResponse

from keeper.app import schemas as S
from keeper.jobs import events as job_events
from keeper.services import jobs

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=S.JobList)
def list_jobs(kind: str | None = None, status: str | None = None, limit: int = 20) -> S.JobList:
    return jobs.list_jobs(kind, status, limit)


@router.get("/jobs/{job_id}", response_model=S.JobOut)
def get_job(job_id: str) -> S.JobOut:
    return jobs.get_job(job_id)


@router.get("/jobs/{job_id}/events", responses={200: {"content": {"text/event-stream": {}}}})
async def events(job_id: str, request: Request, after: int | None = None,
                 last_event_id: str | None = Header(default=None)) -> EventSourceResponse:
    jobs.get_job(job_id)
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else (after or 0)
    return EventSourceResponse(job_events.stream(job_id, start, request), ping=15,
                               headers={"X-Accel-Buffering": "no"})


@router.get("/jobs/{job_id}/log", response_class=Response, responses={200: {"content": {"text/plain": {}}}})
def log(job_id: str) -> Response:
    return Response(jobs.job_log(job_id), media_type="text/plain")


@router.post("/jobs/{job_id}/cancel", response_model=S.JobOut)
def cancel(job_id: str) -> S.JobOut:
    return jobs.cancel(job_id)


@router.post("/jobs/{job_id}/resume", response_model=S.JobAccepted, status_code=202)
def resume(job_id: str) -> S.JobAccepted:
    return jobs.resume(job_id)

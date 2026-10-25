from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import queue

router = APIRouter(tags=["queue"])


@router.get("/projects/{pid}/queue", response_model=S.QueueResponse)
def get_queue(pid: str, lane: str | None = None, sort: Literal["attention", "updated", "number"] = "attention",
              q: str | None = None, ctx: Ctx = Depends(get_ctx)) -> S.QueueResponse:
    return queue.get_queue(pid, lane=lane, sort=sort, q=q)


@router.post("/projects/{pid}/queue/refresh", response_model=S.JobAccepted, status_code=202)
def refresh(pid: str, body: S.QueueRefreshRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return queue.refresh(pid, body, ctx)


@router.get("/projects/{pid}/queue/digest", response_model=S.QueueDigest)
def digest(pid: str) -> S.QueueDigest:
    return queue.digest(pid)

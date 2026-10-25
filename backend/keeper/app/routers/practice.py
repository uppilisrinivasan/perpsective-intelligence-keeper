from __future__ import annotations

from fastapi import APIRouter, Depends

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import practice

router = APIRouter(tags=["practice"])


@router.get("/projects/{pid}/practice/overview", response_model=S.PracticeOverview)
def overview(pid: str, learner: str = "me", ctx: Ctx = Depends(get_ctx)) -> S.PracticeOverview:
    return practice.overview(pid, learner, ctx)


@router.post("/projects/{pid}/practice/sessions", response_model=S.PracticeSessionOut, status_code=201)
def start_session(pid: str, body: S.PracticeStart, ctx: Ctx = Depends(get_ctx)) -> S.PracticeSessionOut:
    return practice.start_session(pid, body, ctx)


@router.get("/practice/sessions/{sid}", response_model=S.PracticeSessionOut)
def get_session(sid: str, ctx: Ctx = Depends(get_ctx)) -> S.PracticeSessionOut:
    return practice.get_session(sid, ctx)


@router.get("/practice/sessions/{sid}/items/{n}", response_model=S.PracticeItemOut)
def get_item(sid: str, n: int, ctx: Ctx = Depends(get_ctx)) -> S.PracticeItemOut:
    return practice.get_item(sid, n, ctx)


@router.post("/practice/sessions/{sid}/items/{n}/answers", response_model=S.PracticeFeedback)
async def submit_answer(sid: str, n: int, body: S.PracticeAnswerRequest, ctx: Ctx = Depends(get_ctx)
                        ) -> S.PracticeFeedback:
    return await practice.submit_answer(sid, n, body, ctx)


@router.get("/practice/sessions/{sid}/items/{n}/feedback", response_model=S.PracticeFeedback)
def get_feedback(sid: str, n: int, ctx: Ctx = Depends(get_ctx)) -> S.PracticeFeedback:
    return practice.get_feedback(sid, n, ctx)


@router.post("/practice/sessions/{sid}/complete", response_model=S.PracticeResult)
def complete(sid: str, ctx: Ctx = Depends(get_ctx)) -> S.PracticeResult:
    return practice.complete(sid, ctx)

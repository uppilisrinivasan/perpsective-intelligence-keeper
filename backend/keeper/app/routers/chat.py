from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sse_starlette.sse import EventSourceResponse

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.assistant import loop
from keeper.services import chat

router = APIRouter(tags=["chat"])


@router.get("/chat/threads", response_model=S.ChatThreadList)
def list_threads(context: str | None = None) -> S.ChatThreadList:
    return chat.list_threads(context)


@router.post("/chat/threads", response_model=S.ChatThreadDetail, status_code=201)
def create_thread(body: S.ChatThreadCreate, ctx: Ctx = Depends(get_ctx)) -> S.ChatThreadDetail:
    return chat.create_thread(body, ctx)


@router.get("/chat/threads/{tid}", response_model=S.ChatThreadDetail)
def get_thread(tid: str) -> S.ChatThreadDetail:
    return chat.get_thread(tid)


@router.patch("/chat/threads/{tid}", response_model=S.ChatThreadDetail)
def patch_thread(tid: str, body: S.ChatThreadPatch) -> S.ChatThreadDetail:
    return chat.rename_thread(tid, body.title)


@router.delete("/chat/threads/{tid}", status_code=204, response_class=Response, response_model=None)
def delete_thread(tid: str) -> None:
    chat.delete_thread(tid)


@router.post("/chat/threads/{tid}/messages", responses={200: {"content": {"text/event-stream": {}}}})
async def send(tid: str, body: S.ChatSend, ctx: Ctx = Depends(get_ctx)) -> EventSourceResponse:
    chat.ensure_thread(tid)
    return EventSourceResponse(loop.answer(tid, body.text, body.context or {}, ctx), ping=15,
                               headers={"X-Accel-Buffering": "no"})


@router.post("/chat/threads/{tid}/stop", status_code=204, response_class=Response, response_model=None)
def stop(tid: str) -> None:
    loop.stop(tid)


@router.get("/chat/suggestions", response_model=S.SuggestionList)
def suggestions(context: str | None = None, number: int | None = None) -> S.SuggestionList:
    return chat.suggestions(context, number)


@router.get("/chat/examples", response_model=S.ChatExampleList)
def examples() -> S.ChatExampleList:
    return chat.examples()

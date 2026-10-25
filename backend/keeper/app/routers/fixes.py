from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import fixes

router = APIRouter(tags=["fixes"])


@router.post("/projects/{pid}/pulls/{n}/fixes", response_model=S.JobAccepted, status_code=202)
def start_fix(pid: str, n: int, body: S.FixRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return fixes.start_fix(pid, n, body, ctx)


@router.get("/projects/{pid}/pulls/{n}/fixes", response_model=S.FixRunList)
def list_fixes(pid: str, n: int) -> S.FixRunList:
    return fixes.list_fixes(pid, n)


@router.get("/fixes/{fix_id}", response_model=S.FixRunDetail)
def get_fix(fix_id: str) -> S.FixRunDetail:
    return fixes.get_fix(fix_id)


@router.get("/fixes/{fix_id}/patch", response_class=Response, responses={200: {"content": {"text/x-diff": {}}}})
def get_patch(fix_id: str) -> Response:
    name, body = fixes.get_patch(fix_id)
    return Response(body, media_type="text/x-diff", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/fixes/{fix_id}/cancel", response_model=S.JobOut)
def cancel_fix(fix_id: str, ctx: Ctx = Depends(get_ctx)) -> S.JobOut:
    return fixes.cancel_fix(fix_id, ctx)

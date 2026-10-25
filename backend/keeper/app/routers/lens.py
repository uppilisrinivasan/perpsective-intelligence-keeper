from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import lens

router = APIRouter(tags=["lens"])


@router.get("/projects/{pid}/lenses", response_model=S.LensList)
def list_lenses(pid: str) -> S.LensList:
    return lens.list_lenses(pid)


@router.get("/lenses/{lid}", response_model=S.LensOverview)
def get_lens(lid: str, ctx: Ctx = Depends(get_ctx)) -> S.LensOverview:
    return lens.get_lens(lid, ctx)


@router.get("/lenses/{lid}/versions/{v}", response_model=S.LensVersionOut)
def get_version(lid: str, v: int, ctx: Ctx = Depends(get_ctx)) -> S.LensVersionOut:
    return lens.get_version(lid, v, ctx)


@router.get("/lenses/{lid}/versions/{v}/items", response_model=S.LensItemList)
def list_items(lid: str, v: int, type: str | None = None, category: str | None = None, status: str | None = None,
               q: str | None = None, ctx: Ctx = Depends(get_ctx)) -> S.LensItemList:
    return lens.list_items(lid, v, type=type, category=category, status=status, q=q, ctx=ctx)


@router.get("/lens-items/{item_id}", response_model=S.LensItemDetail)
def get_item(item_id: str, ctx: Ctx = Depends(get_ctx)) -> S.LensItemDetail:
    return lens.get_item(item_id, ctx)


@router.patch("/lens-items/{item_id}", response_model=S.LensItemOut)
def patch_item(item_id: str, body: S.LensItemPatch, ctx: Ctx = Depends(get_ctx)) -> S.LensItemOut:
    return lens.patch_item(item_id, body, ctx)


@router.get("/lenses/{lid}/diff", response_model=S.LensDiff)
def diff(lid: str, from_: int | None = Query(default=None, alias="from"), to: int | None = None, ctx: Ctx = Depends(get_ctx)) -> S.LensDiff:
    return lens.diff(lid, from_, to, ctx)


@router.post("/lenses/{lid}/rebuild", response_model=S.JobAccepted, status_code=202)
def rebuild(lid: str, body: S.LensActionRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return lens.rebuild(lid, body, ctx)


@router.post("/lenses/{lid}/update", response_model=S.JobAccepted, status_code=202)
def update(lid: str, body: S.LensActionRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return lens.update(lid, body, ctx)


@router.post("/lenses/{lid}/recalibrate", response_model=S.JobAccepted, status_code=202)
def recalibrate(lid: str, body: S.LensActionRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return lens.recalibrate(lid, body, ctx)


@router.post("/lenses/{lid}/pause", response_model=S.LensOverview)
def pause(lid: str, ctx: Ctx = Depends(get_ctx)) -> S.LensOverview:
    return lens.set_status(lid, "paused", ctx)


@router.post("/lenses/{lid}/resume", response_model=S.LensOverview)
def resume(lid: str, ctx: Ctx = Depends(get_ctx)) -> S.LensOverview:
    return lens.set_status(lid, "active", ctx)


@router.post("/lenses/{lid}/revoke", response_model=S.LensOverview)
def revoke(lid: str, body: S.RevokeRequest, ctx: Ctx = Depends(get_ctx)) -> S.LensOverview:
    return lens.revoke(lid, body, ctx)


@router.get("/lenses/{lid}/export", response_class=Response, responses={200: {"content": {"application/zip": {}}}})
def export(lid: str, include_exemplars: bool = False, include_bias: bool = False, format: str = "zip",
           ctx: Ctx = Depends(get_ctx)) -> Response:
    name, body, media = lens.export(lid, include_exemplars=include_exemplars, include_bias=include_bias,
                                    fmt=format, ctx=ctx)
    return Response(body, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/projects/{pid}/lenses/import", response_model=S.LensOverview, status_code=201)
async def import_package(pid: str, file: UploadFile = File(...), ctx: Ctx = Depends(get_ctx)) -> S.LensOverview:
    data = await file.read()
    return lens.import_package(pid, data, file.filename or "lens.zip", ctx)


@router.get("/lenses/{lid}/edge-map", response_model=S.EdgeMapOut)
def edge_map(lid: str, version: int | None = None) -> S.EdgeMapOut:
    return lens.edge_map(lid, version)


@router.get("/lenses/{lid}/bias", response_model=S.BiasList)
def bias(lid: str, ctx: Ctx = Depends(get_ctx)) -> S.BiasList:
    return lens.bias(lid, ctx)


@router.get("/lenses/{lid}/growth", response_model=S.GrowthOut)
def growth(lid: str) -> S.GrowthOut:
    return lens.growth(lid)


@router.get("/lenses/{lid}/audit", response_model=S.AuditList)
def audit(lid: str) -> S.AuditList:
    return lens.audit(lid)

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import settings as svc
from keeper.services import usage

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=S.SettingsOut)
def get_settings_() -> S.SettingsOut:
    return svc.get_settings_out()


@router.patch("/settings", response_model=S.SettingsOut)
def patch_settings(body: dict[str, Any], ctx: Ctx = Depends(get_ctx)) -> S.SettingsOut:
    return svc.patch(body, ctx)


@router.post("/settings/reset", response_model=S.SettingsOut)
def reset_settings_(body: dict[str, Any] | None = None, ctx: Ctx = Depends(get_ctx)) -> S.SettingsOut:
    return svc.reset((body or {}).get("keys"), ctx)


@router.post("/settings/reset-saved-results", response_model=S.JobAccepted, status_code=202)
def reset_saved(ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return svc.reset_live_results(ctx)


@router.get("/usage", response_model=S.UsageOut)
def get_usage(period: Literal["day", "month", "total"] = "month",
              group_by: Literal["model", "feature", "day"] = "feature") -> S.UsageOut:
    return usage.usage(period, group_by)


@router.post("/settings/probe", response_model=S.JobAccepted, status_code=202)
def probe() -> S.JobAccepted:
    return svc.start_probe()


@router.post("/settings/sandbox-check", response_model=S.JobAccepted, status_code=202)
def sandbox_check(ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return svc.start_sandbox_check(ctx)

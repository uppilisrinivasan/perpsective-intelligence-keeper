from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from keeper import __version__
from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import system, tour

router = APIRouter(tags=["system"])


@router.get("/health", response_model=S.Health)
def health() -> S.Health:
    return S.Health(status="ok", version=__version__)


@router.get("/status", response_model=S.Status)
def status() -> S.Status:
    return system.status()


@router.get("/tour", response_model=S.Tour)
def get_tour(ctx: Ctx = Depends(get_ctx)) -> S.Tour:
    return tour.build_tour(None)


@router.get("/glossary", response_model=S.Glossary)
def glossary() -> S.Glossary:
    return system.glossary()


@router.get("/avatars/{person_id}.svg", response_class=Response, responses={200: {"content": {"image/svg+xml": {}}}})
def avatar(person_id: str) -> Response:
    return Response(system.avatar_svg(person_id), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})

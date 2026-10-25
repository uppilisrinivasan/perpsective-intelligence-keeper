from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from keeper.app import auth

router = APIRouter(tags=["auth"])


class SessionRequest(BaseModel):
    access_code: str


class SessionState(BaseModel):
    signed_in: bool
    expires_at: str | None = None
    auth_mode: str


@router.post("/auth/session", status_code=204, response_class=Response, response_model=None)
def sign_in(body: SessionRequest, request: Request, response: Response) -> None:
    auth.sign_in(body.access_code, request, response)


@router.delete("/auth/session", status_code=204, response_class=Response, response_model=None)
def sign_out(response: Response) -> None:
    auth.sign_out(response)


@router.get("/auth/session", response_model=SessionState)
def session_state(request: Request) -> SessionState:
    return SessionState(**auth.session_state(request))

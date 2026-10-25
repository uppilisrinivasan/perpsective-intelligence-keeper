"""Per-request context: viewer role (X-Keeper-Role), request ID, and the guest learner key (cookie)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request

ROLES = ("maintainer", "contributor", "reviewer", "judge")
GUEST_COOKIE = "keeper_guest"


@dataclass
class Ctx:
    role: str
    request_id: str
    guest_key: str
    person_id: str | None = None


def get_ctx(request: Request) -> Ctx:
    role = (request.headers.get("x-keeper-role") or request.query_params.get("role") or "maintainer").lower()
    person = request.headers.get("x-keeper-person")
    if role not in ROLES:
        role = "maintainer"
    guest = request.cookies.get(GUEST_COOKIE) or getattr(request.state, "guest_key", None) or uuid.uuid4().hex
    request.state.guest_key = guest
    return Ctx(role=role, request_id=getattr(request.state, "request_id", "req_local"), guest_key=guest,
               person_id=person)

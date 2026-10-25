"""Cloud access: access code → signed session cookie, CSRF double submit, per-session and per-IP rate limits."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from keeper.config import get_settings
from keeper.core.errors import AuthRequired, Forbidden, RateLimited

COOKIE = "keeper_session"
CSRF_COOKIE = "keeper_csrf"
MAX_AGE = 12 * 3600
_OPEN_PATHS = ("/api/v1/health", "/api/v1/auth/session", "/api/v1/status")


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().KEEPER_SESSION_SECRET.get_secret_value(), salt="keeper-session")


def enabled() -> bool:
    return get_settings().KEEPER_AUTH_MODE == "access_code"


def sign_in(code: str, request: Request, response: Response) -> None:
    if not enabled():
        return
    codes = get_settings().access_codes()
    if not any(hmac.compare_digest(code.strip(), c) for c in codes):
        raise Forbidden("That access code isn't valid.")
    sid = secrets.token_urlsafe(16)
    token = _serializer().dumps({"sid": sid})
    response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, secure=True, samesite="lax")
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(16), max_age=MAX_AGE, httponly=False, secure=True,
                        samesite="lax")


def sign_out(response: Response) -> None:
    response.delete_cookie(COOKIE)
    response.delete_cookie(CSRF_COOKIE)


def _session(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        return _serializer().loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def session_state(request: Request) -> dict:
    s = get_settings()
    if not enabled():
        return {"signed_in": True, "expires_at": None, "auth_mode": s.KEEPER_AUTH_MODE}
    return {"signed_in": _session(request) is not None, "expires_at": None, "auth_mode": s.KEEPER_AUTH_MODE}


_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate(key: str, limit: int) -> None:
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise RateLimited("Too many requests.", {"retry_after": int(60 - (now - q[0])) + 1})
    q.append(now)


def check(request: Request) -> None:
    """Called by the middleware for /api paths in cloud mode."""
    if not enabled():
        return
    path = request.url.path
    ip = request.client.host if request.client else "?"
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    limit = get_settings().API_RATE_LIMIT_PER_MINUTE
    _rate("ip:" + ip_hash, limit * 2)
    if any(path.startswith(p) for p in _OPEN_PATHS):
        return
    sess = _session(request)
    if sess is None:
        raise AuthRequired("Sign in with an access code.")
    _rate("s:" + sess["sid"], limit)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        header = request.headers.get("x-keeper-csrf", "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not header or not hmac.compare_digest(header, cookie):
            raise Forbidden("Missing or invalid CSRF token.")

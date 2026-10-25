"""FastAPI app factory: REST under /api/v1, SSE for jobs and chat, the built frontend at /."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from keeper import __version__
from keeper.config import get_settings
from keeper.core.errors import KeeperError

API = "/api/v1"

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; "
       "font-src 'self' data:; frame-ancestors 'none'")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    from keeper.services import startup

    await startup.on_startup()
    try:
        yield
    finally:
        await startup.on_shutdown()


def create_app(*, run_startup: bool = True) -> FastAPI:
    # routers are imported here, not at module import, so `keeper.app.schemas` can be used by services without
    # pulling in the whole API (and the import cycle routers → services → schemas → app)
    from keeper.app import auth, errors, static
    from keeper.app.routers import auth as auth_router
    from keeper.app.routers import (
        chat,
        fixes,
        jobs,
        lens,
        practice,
        projects,
        proof,
        pulls,
        queue,
        settings,
        system,
    )

    s = get_settings()
    app = FastAPI(title="Keeper API", version=__version__, openapi_url=f"{API}/openapi.json",
                  docs_url="/api/docs" if s.API_DOCS else None, redoc_url=None,
                  lifespan=lifespan if run_startup else None)
    errors.install(app)

    if s.KEEPER_AUTH_MODE == "none":
        app.add_middleware(CORSMiddleware, allow_origins=[f"http://127.0.0.1:{s.FRONTEND_DEV_PORT}",
                                                          f"http://localhost:{s.FRONTEND_DEV_PORT}"],
                           allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = rid
        if request.url.path.startswith("/api/"):
            try:
                auth.check(request)
            except KeeperError as e:
                return JSONResponse({"error": {"code": e.code, "message": e.message, "details": e.details,
                                               "request_id": rid}}, status_code=e.http_status)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if not request.url.path.startswith("/api/docs"):
            response.headers["Content-Security-Policy"] = CSP
        if s.KEEPER_AUTH_MODE == "access_code":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        guest = getattr(request.state, "guest_key", None)
        if guest and "keeper_guest" not in request.cookies:
            response.set_cookie("keeper_guest", guest, max_age=180 * 86400, httponly=True, samesite="lax")
        return response

    for r in (system, auth_router, projects, queue, pulls, fixes, lens, proof, practice, chat, jobs, settings):
        app.include_router(r.router, prefix=API)
    static.mount(app)
    return app


def run_coroutine(coro):  # type: ignore[no-untyped-def]
    return asyncio.get_event_loop().run_until_complete(coro)

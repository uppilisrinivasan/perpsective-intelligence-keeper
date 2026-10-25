"""Map domain errors to the API error envelope (docs/05-api/01-conventions.md §4)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from keeper.core.errors import KeeperError
from keeper.logging import get_logger

log = get_logger("keeper.api")


def _body(code: str, message: str, details: dict, request: Request) -> dict:
    return {"error": {"code": code, "message": message, "details": details,
                      "request_id": getattr(request.state, "request_id", None)}}


def install(app: FastAPI) -> None:
    @app.exception_handler(KeeperError)
    async def keeper_error(request: Request, exc: KeeperError) -> JSONResponse:
        headers = {}
        if exc.http_status in (429, 503) and exc.details.get("retry_after"):
            headers["Retry-After"] = str(int(exc.details["retry_after"]))
        return JSONResponse(_body(exc.code, exc.message, exc.details, request), status_code=exc.http_status,
                            headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(_body("validation_failed", "Some fields are invalid.", {"fields": fields}, request),
                            status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 401: "auth_required", 403: "forbidden"}.get(
            exc.status_code, "error")
        return JSONResponse(_body(code, str(exc.detail), {}, request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(_body("error", "Something went wrong.", {}, request), status_code=500)

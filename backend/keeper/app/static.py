"""Serve the built frontend (frontend/dist) with an SPA fallback to index.html."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles

from keeper.config import ROOT


def dist_dir() -> Path:
    return ROOT / "frontend" / "dist"


def mount(app: FastAPI) -> None:
    dist = dist_dir()
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):  # type: ignore[no-untyped-def]
        if path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(404, "Not found")
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(str(f))
        index = dist / "index.html"
        if index.exists():
            return FileResponse(str(index), headers={"Cache-Control": "no-cache"})
        return HTMLResponse("<!doctype html><title>Keeper</title><p>The frontend isn't built yet. "
                            "Run <code>./run.sh</code> (it builds it), or use <code>./run.sh --dev</code>.</p>")

"""Tests run offline: LLM_PROVIDER=fake and a throwaway runtime directory (never the developer's .runtime/)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_RT = tempfile.mkdtemp(prefix="keeper-test-")
os.environ["KEEPER_RUNTIME_DIR"] = _RT
os.environ["LLM_PROVIDER"] = "fake"
os.environ.pop("NEBIUS_API_KEY", None)
os.environ.pop("LLM_API_KEY", None)

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def demo():
    """The demo world with the committed snapshot, loaded once into the test runtime."""
    from keeper.db.__main__ import upgrade
    from keeper.db.session import session_scope
    from keeper.ingest.demo import load_demo

    if not (ROOT / "data" / "snapshots" / "prj_demo" / "snapshot.json").exists():
        pytest.skip("no committed snapshot (run ./run.sh --snapshot)")
    upgrade()
    with session_scope() as db:
        p = load_demo(db)
        return p.id


@pytest.fixture()
def client(demo):
    from fastapi.testclient import TestClient
    from sse_starlette.sse import AppStatus

    from keeper.app import create_app
    AppStatus.should_exit_event = None  # sse-starlette binds this to the first loop; TestClient uses one per request
    with TestClient(create_app(run_startup=False), raise_server_exceptions=False) as c:
        yield c

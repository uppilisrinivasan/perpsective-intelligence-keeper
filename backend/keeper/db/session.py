"""Engine and sessions. SQLite: WAL mode and foreign keys on."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from keeper.config import get_settings


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, pool_pre_ping=True)

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

        return eng
    return create_engine(url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = get_settings()
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    return make_engine(s.database_url)


@lru_cache(maxsize=1)
def _factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def reset_engine() -> None:
    with suppress(Exception):
        get_engine().dispose()
    get_engine.cache_clear()
    _factory.cache_clear()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = _factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def new_session() -> Session:
    return _factory()()

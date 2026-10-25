"""Write-behind for side-channel rows (LLM audit, cache, job events and progress).

SQLite allows one writer at a time. A pipeline holds a write transaction while it works, and must not be blocked
by (or block) the gateway's audit rows or the job's event rows. Those go through this queue: callers never wait,
and a background thread writes them in order, retrying while the database is busy. `flush()` waits for the queue.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import OperationalError

from keeper.logging import get_logger

log = get_logger("keeper.db")
_q: queue.Queue[Callable[[Any], None] | None] = queue.Queue()
_thread: threading.Thread | None = None
_lock = threading.Lock()
_pending = 0
_done = threading.Condition()


def _worker() -> None:
    global _pending
    from keeper.db.session import new_session

    while True:
        op = _q.get()
        if op is None:
            return
        for attempt in range(200):
            db = new_session()
            try:
                op(db)
                db.commit()
                break
            except OperationalError as e:
                db.rollback()
                if "locked" not in str(e) and "busy" not in str(e):
                    log.error("side-channel write failed: %s", e)
                    break
                time.sleep(min(0.05 * (attempt + 1), 1.0))
            except Exception as e:  # noqa: BLE001
                db.rollback()
                log.error("side-channel write failed: %s", e)
                break
            finally:
                db.close()
        with _done:
            _pending -= 1
            _done.notify_all()


def submit(op: Callable[[Any], None]) -> None:
    global _thread, _pending
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_worker, name="keeper-sidecar", daemon=True)
            _thread.start()
    with _done:
        _pending += 1
    _q.put(op)


def add(obj: Any) -> None:
    submit(lambda db: db.merge(obj))


def flush(timeout: float = 60.0) -> bool:
    end = time.time() + timeout
    with _done:
        while _pending > 0:
            left = end - time.time()
            if left <= 0:
                return False
            _done.wait(timeout=left)
    return True

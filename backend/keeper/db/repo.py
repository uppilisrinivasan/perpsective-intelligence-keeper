"""Small persistence helpers shared by the pipelines (findings ↔ rows, app state)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.core.types import Anchor, Finding
from keeper.db import models as M


def short_title(statement: str, words: int = 9) -> str:
    s = statement.strip().rstrip(".")
    for sep in (": ", "; ", " — ", ", because", " because ", ", so "):
        if sep in s and len(s.split(sep)[0].split()) >= 3:
            s = s.split(sep)[0]
            break
    parts = s.split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def to_row(f: Finding, *, origin: str = "live", context: str = "history", ruler_id: str | None = None,
           lens_version_id: str | None = None, practice_answer_id: str | None = None,
           title: str | None = None) -> M.FindingRow:
    a = f.anchor
    return M.FindingRow(id=f.id, project_id=f.project_id, pr_number=f.pr_number, head_sha=f.head_sha, source=f.source,
                        person_id=f.person_id, ruler_id=ruler_id, lens_version_id=lens_version_id,
                        practice_answer_id=practice_answer_id, scope=a.scope, path=a.path, side=a.side,
                        start_line=a.start_line, end_line=a.end_line, category=f.category, severity=f.severity,
                        kind=f.kind, title=title or short_title(f.statement), statement=f.statement,
                        rationale=f.rationale, suggestion=f.suggestion, substantive=f.substantive,
                        confidence=f.confidence, refs=f.refs, llm_call_id=f.llm_call_id, context=context,
                        origin=origin, created_at=f.created_at)


def from_row(r: M.FindingRow) -> Finding:
    return Finding(id=r.id, project_id=r.project_id, pr_number=r.pr_number, head_sha=r.head_sha, source=r.source,
                   person_id=r.person_id, anchor=Anchor(scope=r.scope, path=r.path, side=r.side,
                                                        start_line=r.start_line, end_line=r.end_line),
                   category=r.category, severity=r.severity, kind=r.kind, statement=r.statement,
                   rationale=r.rationale, suggestion=r.suggestion, substantive=r.substantive,
                   confidence=r.confidence, refs=dict(r.refs or {}), llm_call_id=r.llm_call_id,
                   created_at=r.created_at)


def findings(db: Session, project_id: str, *, pr_number: int | None = None, source: str | None = None,
             person_id: str | None = None, lens_version_id: str | None = None, context: str | None = None,
             ruler_id: str | None = None, head_sha: str | None = None) -> list[Finding]:
    q = select(M.FindingRow).where(M.FindingRow.project_id == project_id)
    for col, val in ((M.FindingRow.pr_number, pr_number), (M.FindingRow.source, source),
                     (M.FindingRow.person_id, person_id), (M.FindingRow.lens_version_id, lens_version_id),
                     (M.FindingRow.context, context), (M.FindingRow.ruler_id, ruler_id),
                     (M.FindingRow.head_sha, head_sha)):
        if val is not None:
            q = q.where(col == val)
    return [from_row(r) for r in db.execute(q.order_by(M.FindingRow.created_at, M.FindingRow.id)).scalars()]


def get_state(db: Session, key: str, default: Any = None) -> Any:
    row = db.get(M.AppState, key)
    return row.value if row else default


def set_state(db: Session, key: str, value: Any) -> None:
    row = db.get(M.AppState, key)
    if row:
        row.value = value
        row.updated_at = datetime.now(UTC)
    else:
        db.add(M.AppState(key=key, value=value))


def audit(db: Session, actor_role: str, action: str, object_type: str, object_id: str,
          details: dict[str, Any] | None = None) -> None:
    from keeper.ids import new_id
    db.add(M.AuditEvent(id=new_id("aud"), actor_role=actor_role, action=action, object_type=object_type,
                        object_id=object_id, details=details or {}))


_state_cache: dict[str, tuple[float, Any]] = {}


def get_state_cached(key: str, ttl: float = 5.0) -> Any:
    """App state read through a short in-process cache (used on hot read paths such as provenance)."""
    import time

    from keeper.db.session import session_scope

    hit = _state_cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    with session_scope() as db:
        v = get_state(db, key)
    _state_cache[key] = (time.time(), v)
    return v


def invalidate_state_cache(key: str | None = None) -> None:
    if key is None:
        _state_cache.clear()
    else:
        _state_cache.pop(key, None)

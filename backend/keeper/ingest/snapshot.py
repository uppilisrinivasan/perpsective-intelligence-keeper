"""Saved analysis snapshots (data/snapshots/<project>/): export every analysis table as JSON Lines, and load them
back with origin = snapshot (FR-DATA-4). Reads prefer live rows when both exist."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from keeper.db import models as M

# Load order respects foreign keys.
TABLES: list[type[M.Base]] = [
    M.Ruler, M.FindingRow, M.FindingMatch, M.ResidualSample, M.Outcome, M.OutcomeLink, M.Consent, M.Lens,
    M.LensVersion, M.LensItemRow, M.LensItemEvidence, M.BiasCheck, M.EdgeMapCell, M.GrowthSnapshot, M.Analysis,
    M.RoutedFindingRow, M.Handoff, M.ReviewDraft, M.FixRun, M.FixAttempt, M.FidelityRun, M.FidelityCase,
    M.PracticeSession, M.PracticeAnswer, M.ChatThread, M.ChatMessage, M.LLMCall, M.AuditEvent,
]
SKIP_COLUMNS = {M.LLMCall: {"job_id"}, M.FixRun: {"job_id"}, M.Analysis: {"job_id"}, M.LensVersion: {"job_id"},
                M.FidelityRun: {"job_id"}}


def _ser(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def export(db: Session, out: Path, project_id: str) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for t in TABLES:
        cols = [c.key for c in inspect(t).mapper.column_attrs]
        skip = SKIP_COLUMNS.get(t, set())
        rows = db.execute(select(t)).scalars().all()
        lines = []
        for r in rows:
            d = {c: _ser(getattr(r, c)) for c in cols if c not in skip}
            lines.append(json.dumps(d, sort_keys=True, ensure_ascii=False, default=str))
        (out / f"{t.__tablename__}.jsonl").write_text("".join(x + "\n" for x in lines), encoding="utf-8")
        counts[t.__tablename__] = len(lines)
    return counts


def load(db: Session, src: Path) -> dict[str, int]:
    from keeper.core.timeutil import parse_ts

    counts = {}
    # snapshot rows replace earlier snapshot rows; live rows are kept
    for t in reversed(TABLES):
        if "origin" in t.__table__.c:
            db.execute(delete(t).where(t.__table__.c.origin == "snapshot"))
    db.flush()
    for t in TABLES:
        f = src / f"{t.__tablename__}.jsonl"
        if not f.exists():
            continue
        dt_cols = {c.key for c in inspect(t).mapper.column_attrs
                   if c.columns[0].type.__class__.__name__ in ("UTCDateTime", "DateTime")}
        n = 0
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            for c in dt_cols:
                if d.get(c):
                    d[c] = parse_ts(d[c])
            if "origin" in t.__table__.c:
                d["origin"] = "snapshot"
            obj = t(**d)
            db.merge(obj)
            n += 1
        db.flush()
        counts[t.__tablename__] = n
    return counts

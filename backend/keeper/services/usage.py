"""GET /usage: calls, tokens and cost by model, feature or day, against the spend cap."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select

from keeper.app import schemas as S
from keeper.config import get_config
from keeper.db import models as M
from keeper.db import sidecar
from keeper.db.session import session_scope
from keeper.llm import meter


def _rows(calls: list[M.LLMCall], group_by: str) -> list[S.UsageRow]:
    cfg = get_config()
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                                         "cost_usd": 0.0})
    for c in calls:
        k = {"model": cfg.model_display(c.model_id), "feature": c.feature,
             "day": c.at.date().isoformat() if c.at else "?"}[group_by]
        a = agg[k]
        a["calls"] += 1
        a["input_tokens"] += c.input_tokens
        a["output_tokens"] += c.output_tokens
        a["cost_usd"] += c.cost_usd
    return [S.UsageRow(key=k, **{**v, "cost_usd": round(v["cost_usd"], 4)}) for k, v in sorted(agg.items())]


def usage(period: str, group_by: str) -> S.UsageOut:
    sidecar.flush(5)
    start = meter.period_start(period)
    with session_scope() as db:
        q = select(M.LLMCall)
        if start is not None:
            q = q.where(M.LLMCall.at >= start)
        calls = db.execute(q).scalars().all()
        live = [c for c in calls if c.origin == "live"]
        snap = db.execute(select(M.LLMCall).where(M.LLMCall.origin == "snapshot")).scalars().all()
    rows = _rows(live, group_by)
    total = S.UsageRow(key="total", calls=sum(r.calls for r in rows), input_tokens=sum(r.input_tokens for r in rows),
                       output_tokens=sum(r.output_tokens for r in rows),
                       cost_usd=round(sum(r.cost_usd for r in rows), 4))
    st = meter.spend_status()
    return S.UsageOut(period=period, group_by=group_by, rows=rows, total=total,
                      cap=S.SpendStatus(**st, reached=st["used_usd"] >= st["cap_usd"]),
                      snapshot_rows=_rows(snap, group_by))

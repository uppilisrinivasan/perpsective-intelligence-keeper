"""Costs from config/pricing.yaml, spend-cap checks and the audit rows (llm_calls)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from keeper.config import get_config, get_settings
from keeper.core.errors import SpendCapReached
from keeper.db.models import LLMCall
from keeper.db.session import session_scope


def price(model_id: str) -> tuple[float, float]:
    p = get_config().pricing
    table = p["per_million_tokens"]
    if model_id in table:
        return float(table[model_id]["input"]), float(table[model_id]["output"])
    # unknown_model_policy: most_expensive — an unknown model is never free by accident
    worst = max(table.values(), key=lambda v: v["input"] + v["output"])
    return float(worst["input"]), float(worst["output"])


def cost(model_id: str, input_tokens: int, output_tokens: int, reasoning_tokens: int = 0) -> float:
    pi, po = price(model_id)
    return round((input_tokens * pi + (output_tokens + reasoning_tokens) * po) / 1_000_000, 6)


def period_start(period: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None


def period_reset(period: str, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    start = period_start(period, now)
    if start is None:
        return None
    if period == "day":
        return start + timedelta(days=1)
    nxt = start.replace(year=start.year + (start.month // 12), month=start.month % 12 + 1)
    return nxt


def spent(period: str | None = None) -> float:
    from keeper.db import sidecar
    sidecar.flush(5)
    s = get_settings()
    period = period or s.KEEPER_SPEND_CAP_PERIOD
    start = period_start(period)
    with session_scope() as db:
        q = select(func.coalesce(func.sum(LLMCall.cost_usd), 0.0)).where(LLMCall.origin == "live",
                                                                       LLMCall.cache_hit.is_(False))
        if start is not None:
            q = q.where(LLMCall.at >= start)
        return float(db.execute(q).scalar_one())


def tokens_today() -> int:
    start = period_start("day")
    with session_scope() as db:
        q = select(func.coalesce(func.sum(LLMCall.input_tokens + LLMCall.output_tokens), 0)).where(
            LLMCall.at >= start, LLMCall.origin == "live", LLMCall.cache_hit.is_(False))
        return int(db.execute(q).scalar_one())


def check_spend(estimate_usd: float) -> None:
    s = get_settings()
    cap = s.KEEPER_SPEND_CAP_USD
    used = spent()
    if used + estimate_usd > cap:
        raise SpendCapReached(
            f"Keeper reached its ${cap:g} spending limit for this {s.KEEPER_SPEND_CAP_PERIOD}.",
            {"cap": cap, "period": s.KEEPER_SPEND_CAP_PERIOD, "used": round(used, 4),
             "resets_at": (r.isoformat() if (r := period_reset(s.KEEPER_SPEND_CAP_PERIOD)) else None)})


def spend_status() -> dict[str, Any]:
    s = get_settings()
    r = period_reset(s.KEEPER_SPEND_CAP_PERIOD)
    return {"used_usd": round(spent(), 4), "cap_usd": s.KEEPER_SPEND_CAP_USD, "period": s.KEEPER_SPEND_CAP_PERIOD,
            "resets_at": r.isoformat() if r else None}


_recent: list[dict[str, Any]] = []


def record(row: dict[str, Any]) -> None:
    """Audit row for one call (write-behind, so a pipeline's open transaction never blocks it)."""
    from keeper.db import sidecar
    _recent.append(row)
    if len(_recent) > 500:
        del _recent[:250]
    sidecar.add(LLMCall(**row))

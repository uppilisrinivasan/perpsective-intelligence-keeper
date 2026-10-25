"""Pick the sandbox provider: SANDBOX_PROVIDER, else walk config/sandbox.yaml fallback_order. A fix run never
switches provider midway."""

from __future__ import annotations

from typing import Any

from keeper.config import get_config, get_settings
from keeper.sandbox.contree import ContreeRunner
from keeper.sandbox.docker import DockerRunner
from keeper.sandbox.local import LocalRunner

_RUNNERS = {"local": LocalRunner, "docker": DockerRunner, "contree": ContreeRunner}
_cache: dict[str, Any] = {}


async def select() -> tuple[Any, str | None, str]:
    """Return (runner, reason if the requested provider was not used, requested provider)."""
    want = get_settings().SANDBOX_PROVIDER
    order = [want] + [p for p in get_config().sandbox.get("fallback_order", []) if p != want]
    reasons = []
    for name in order:
        runner = _RUNNERS[name]()
        av = await runner.available()
        if av.ok:
            reason = None if name == want else "; ".join(reasons)
            _cache["last"] = {"provider": name, "requested": want, "reason": reason, "isolation": runner.isolation}
            return runner, reason, want
        reasons.append(f"{name}: {av.reason}")
    runner = LocalRunner()
    return runner, "; ".join(reasons), want


def last_selection() -> dict[str, Any] | None:
    return _cache.get("last")

"""GET/PATCH /settings: effective non-secret settings, editable overrides from config/ui.yaml, secret booleans."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_config, get_settings
from keeper.core.errors import Forbidden, ValidationFailed
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.services.common import job_ref

SECRETS = ["NEBIUS_API_KEY", "LLM_API_KEY", "GITHUB_TOKEN", "TAVILY_API_KEY", "CONTREE_API_KEY"]
_cache: dict[str, Any] | None = None


def overrides() -> dict[str, Any]:
    global _cache
    if _cache is None:
        with session_scope() as db:
            _cache = {r.key: r.value for r in db.execute(select(M.SettingsOverride)).scalars()}
    return _cache


def override(key: str) -> Any:
    return overrides().get(key)


def _coerce(spec: dict[str, Any], v: Any) -> Any:
    t = spec["type"]
    try:
        if t == "int":
            v = int(v)
        elif t == "float":
            v = float(v)
        elif t == "bool":
            v = bool(v) if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        elif t == "enum":
            if str(v) not in [str(o) for o in spec["options"]]:
                raise ValueError
            v = str(v)
    except (TypeError, ValueError) as e:
        raise ValidationFailed(f"Invalid value for {spec.get('label', 'setting')}.") from e
    if t in ("int", "float") and ("min" in spec and v < spec["min"] or "max" in spec and v > spec["max"]):
        raise ValidationFailed(f"{spec.get('label')} must be between {spec['min']} and {spec['max']}.")
    return v


def get_settings_out() -> S.SettingsOut:
    s = get_settings()
    ed = get_config().ui["editable_settings"]
    ov = overrides()
    editable = []
    for key, spec in ed.items():
        default = _coerce(spec, spec["default"])
        editable.append(S.EditableSetting(key=key, label=spec.get("label", key), type=spec["type"],
                                          value=ov.get(key, default), default=default, min=spec.get("min"),
                                          max=spec.get("max"), options=[str(o) for o in spec.get("options", [])] or None))
    from keeper.sandbox.select import last_selection
    sel = last_selection() or {}
    readonly = {"mode": s.KEEPER_MODE, "provider": s.LLM_PROVIDER, "spend_cap_usd": s.KEEPER_SPEND_CAP_USD,
                "spend_cap_period": s.KEEPER_SPEND_CAP_PERIOD, "sandbox_provider": sel.get("provider", s.SANDBOX_PROVIDER),
                "sandbox_reason": sel.get("reason"), "isolation": sel.get("isolation"), "test_recipe": "python-pytest",
                "job_runner": s.JOB_RUNNER, "batch_api": s.BATCH_API_ENABLED, "import_allowed": s.IMPORT_ALLOWED,
                "embeddings": s.EMBEDDINGS_PROVIDER}
    secrets = {k.lower(): S.SecretState(configured=bool(getattr(s, k).get_secret_value())) for k in SECRETS}
    return S.SettingsOut(editable=editable, readonly=readonly, secrets=secrets)


def patch(body: dict[str, Any], ctx: Ctx) -> S.SettingsOut:
    global _cache
    if ctx.role not in ("maintainer", "judge"):
        raise Forbidden("Only the maintainer can change settings.")
    ed = get_config().ui["editable_settings"]
    with session_scope() as db:
        for k, v in body.items():
            if k not in ed:
                raise ValidationFailed(f"{k} is not an editable setting.")
            val = _coerce(ed[k], v)
            row = db.get(M.SettingsOverride, k)
            if row:
                row.value = val
            else:
                db.add(M.SettingsOverride(key=k, value=val))
    _cache = None
    return get_settings_out()


def reset(keys: list[str] | None, ctx: Ctx) -> S.SettingsOut:
    global _cache
    with session_scope() as db:
        q = delete(M.SettingsOverride)
        if keys:
            q = q.where(M.SettingsOverride.key.in_(keys))
        db.execute(q)
    _cache = None
    return get_settings_out()


def reset_live_results(ctx: Ctx) -> S.JobAccepted:
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("reset_live", {}, key="reset_live")
    return job_ref(jid, "reset_live", existing)


def start_probe() -> S.JobAccepted:
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("probe", {}, key="probe")
    return job_ref(jid, "probe", existing)


def start_sandbox_check(ctx: Ctx) -> S.JobAccepted:
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("sandbox_check", {}, key="sandbox_check")
    return job_ref(jid, "sandbox_check", existing)

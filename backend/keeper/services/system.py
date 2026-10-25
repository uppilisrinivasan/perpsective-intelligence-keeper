"""GET /status, /glossary, /avatars (docs/05-api/02 §1)."""

from __future__ import annotations

import hashlib

from sqlalchemy import select

from keeper import __version__
from keeper.app import schemas as S
from keeper.config import get_config, get_settings
from keeper.db import models as M
from keeper.db import repo as R
from keeper.db.session import session_scope
from keeper.llm import meter
from keeper.llm.gateway import get_gateway
from keeper.sandbox.select import last_selection

PURPOSE = {"fast": "Fast: reading history and quick checks", "judge": "Judge: reviews and matching",
           "deep": "Deep: building the lens and writing fixes", "assistant": "Assistant (Ask)"}


def status() -> S.Status:
    s = get_settings()
    cfg = get_config()
    gw = get_gateway()
    probe = gw.probe.get("models", {})
    fb = gw.fallback_active() if s.live else {}
    models = []
    for role, _spec in cfg.models["roles"].items():
        mid = gw.model_for(role)
        p = probe.get(mid, {})
        models.append(S.ModelStatus(role=role, model_id=mid, display=cfg.model_display(mid), purpose=PURPOSE.get(role, role),
                                    probe=S.ProbeResult(**{k: str(v) for k, v in p.items() if k in S.ProbeResult.model_fields}),
                                    fallback_active=role in fb, fallback_model=fb.get(role) or None))
    sel = last_selection() or {}
    with session_scope() as db:
        proj = db.execute(select(M.Project).order_by(M.Project.created_at)).scalars().first()
        snap = R.get_state(db, "snapshot") or {}
        loading = R.get_state(db, "load_demo") or {}
        manifest_sha = R.get_state(db, "manifest_sha")
        loaded_at = R.get_state(db, "loaded_at")
    spend = meter.spend_status()
    return S.Status(
        mode=s.KEEPER_MODE, provider=s.LLM_PROVIDER, live=s.live, simulated=gw.fake,
        reason_if_not_live=s.reason_if_not_live, auth_mode=s.KEEPER_AUTH_MODE,
        default_project_id=proj.id if proj else None, demo_now=proj.demo_now if proj else None, models=models,
        sandbox=S.SandboxStatus(provider=sel.get("provider", s.SANDBOX_PROVIDER), requested=s.SANDBOX_PROVIDER,
                                reason=sel.get("reason"), isolation=sel.get("isolation", "")),
        spend=S.SpendStatus(**spend, reached=spend["used_usd"] >= spend["cap_usd"]),
        data=S.DataStatus(manifest_sha=manifest_sha, loaded_at=loaded_at, snapshot=bool(snap),
                          snapshot_created_at=snap.get("created_at"), snapshot_simulated=bool(snap.get("simulated")),
                          snapshot_models=snap.get("models", []), loading=loading.get("status") == "running",
                          load_job_id=loading.get("job_id"), error=loading.get("error")),
        estimates={k: float(v) for k, v in cfg.ui.get("estimates", {}).items()},
        auto_approve_usd=float(s.KEEPER_AUTO_APPROVE_USD), batch_enabled=s.BATCH_API_ENABLED,
        import_allowed=s.IMPORT_ALLOWED, version=__version__)


def glossary() -> S.Glossary:
    return S.Glossary(terms=[S.GlossaryTerm(**t) for t in get_config().glossary["terms"]])


def avatar_svg(person_id: str) -> str:
    with session_scope() as db:
        p = db.get(M.Person, person_id)
        label = (p.display_name or p.login) if p else "?"
    initials = "".join(w[0] for w in label.replace("-", " ").split()[:2]).upper() or "?"
    hue = int(hashlib.sha256(person_id.encode()).hexdigest()[:4], 16) % 360
    for lane_hue in (55, 160, 250, 300):  # stay clear of the lane hues
        if abs(hue - lane_hue) < 20:
            hue = (hue + 40) % 360
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" role="img" aria-label="{label}">'
            f'<circle cx="20" cy="20" r="20" fill="hsl({hue},45%,42%)"/>'
            f'<text x="20" y="25" text-anchor="middle" font-family="system-ui,sans-serif" font-size="15" '
            f'font-weight="600" fill="#fff">{initials}</text></svg>')

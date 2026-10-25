"""Helpers shared by the services: lookups, provenance, live/saved preference, and the confirmation flow."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.app import schemas as S
from keeper.config import get_config, get_settings
from keeper.core.errors import ConfirmationRequired, NoApiKey, NotFound
from keeper.db import models as M
from keeper.db import repo as R


def project(db: Session, pid: str | None) -> M.Project:
    if pid in (None, "", "default"):
        p = db.execute(select(M.Project).order_by(M.Project.created_at)).scalars().first()
    else:
        p = db.get(M.Project, pid)
    if p is None:
        raise NotFound("Project not found.")
    return p


def pull(db: Session, p: M.Project, n: int) -> M.Pull:
    pr = db.execute(select(M.Pull).where(M.Pull.project_id == p.id, M.Pull.number == n)).scalars().first()
    if pr is None:
        raise NotFound(f"Pull request #{n} not found.")
    return pr


def maintainer(db: Session, p: M.Project) -> M.Person:
    m = db.get(M.Person, p.primary_maintainer_id) if p.primary_maintainer_id else None
    if m is None:
        m = db.execute(select(M.Person).where(M.Person.project_id == p.id, M.Person.role == "maintainer")).scalars().first()
    if m is None:
        raise NotFound("This project has no maintainer yet.")
    return m


def person_ref(pe: M.Person | None) -> S.PersonRef | None:
    if pe is None:
        return None
    return S.PersonRef(id=pe.id, login=pe.login, display_name=pe.display_name, role=pe.role)


def name_of(pe: M.Person | None) -> str:
    return (pe.display_name or pe.login) if pe else ""


def lens_of(db: Session, p: M.Project, person_id: str) -> M.Lens | None:
    return db.execute(select(M.Lens).where(M.Lens.project_id == p.id, M.Lens.person_id == person_id)).scalars().first()


def current_version(db: Session, lens: M.Lens | None) -> M.LensVersion | None:
    if lens is None:
        return None
    return db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id, M.LensVersion.status == "ready")
                      .order_by(M.LensVersion.version.desc())).scalars().first()


def fake_model() -> str:
    return str(get_config().models.get("fake_model_id", "offline-simulator"))


def is_simulated(models: list[str] | None) -> bool:
    return bool(models) and fake_model() in (models or [])


def provenance(origin: str, computed_at: datetime | None, ruler_id: str | None = None, lens_version: int | None = None,
               models: list[str] | None = None) -> S.Provenance:
    cfg = get_config()
    ms = [m for m in (models or []) if m]
    snap = R.get_state_cached("snapshot") or {}
    simulated = is_simulated(ms) or (origin == "snapshot" and bool(snap.get("simulated")))
    return S.Provenance(origin="snapshot" if origin == "snapshot" else "live", computed_at=computed_at,
                        ruler_id=ruler_id, lens_version=lens_version, models=ms,
                        model_displays=[cfg.model_display(m) for m in ms], simulated=simulated)


def prefer_live(rows: list[Any]) -> Any | None:
    """Live rows win over saved (snapshot) rows; among them the newest."""
    if not rows:
        return None
    live = [r for r in rows if getattr(r, "origin", "live") == "live"]
    pool = live or rows
    epoch = datetime.fromtimestamp(0).astimezone()
    return max(pool, key=lambda r: getattr(r, "created_at", None) or epoch)


def require_live() -> None:
    if not get_settings().live:
        raise NoApiKey("This needs a Nemotron API key.", {"how": "Put NEBIUS_API_KEY=<key> in .env and restart "
                                                                  "(./run.sh --check shows the result)."})


# --------------------------------------------------------------------------------------------- confirmations
_tokens: dict[str, tuple[str, float]] = {}


def _params_hash(action: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"a": action, "p": params}, sort_keys=True, default=str).encode()).hexdigest()


def auto_approve_usd(db: Session | None = None) -> float:
    from keeper.services.settings import override
    v = override("auto_approve_usd")
    return float(v) if v is not None else float(get_settings().KEEPER_AUTO_APPROVE_USD)


def confirm(action: str, params: dict[str, Any], estimate: float, token: str | None, label: str) -> None:
    """Raise 402 confirmation_required with a token unless the estimate is under auto-approve or the token
    (valid 10 minutes, bound to these parameters) is presented."""
    from keeper.llm.gateway import get_gateway
    if get_gateway().fake:
        return
    if estimate <= auto_approve_usd():
        return
    h = _params_hash(action, params)
    now = time.time()
    for k in [k for k, (_, exp) in _tokens.items() if exp < now]:
        _tokens.pop(k, None)
    if token and token in _tokens and _tokens[token][0] == h:
        _tokens.pop(token, None)
        return
    t = "cfm_" + secrets.token_urlsafe(12)
    _tokens[t] = (h, now + 600)
    raise ConfirmationRequired(f"{label}: about ${estimate:.2f}. Confirm to continue.",
                               {"estimate_usd": round(estimate, 4), "confirm_token": t, "action": action})


def estimate(key: str, n: float = 1.0) -> float:
    return float(get_config().ui.get("estimates", {}).get(key, 0.01)) * n


def job_ref(job_id: str, kind: str, existing: bool = False) -> S.JobAccepted:
    return S.JobAccepted(job=S.JobRef(id=job_id, kind=kind, status="queued", events_url=f"/api/v1/jobs/{job_id}/events",
                                      existing=existing))


def html_url(p: M.Project, path: str) -> str | None:
    if p.fictional:
        return None
    return f"https://github.com/{p.owner}/{p.repo}/{path}"

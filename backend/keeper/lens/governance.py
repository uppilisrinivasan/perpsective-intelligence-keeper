"""Ownership and consent (methodology 13 §3–§7): no lens without consent; pause, resume and revoke; the audit."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.db import models as M
from keeper.db import repo as R
from keeper.ids import new_id


def active_consent(db: Session, project_id: str, person_id: str, scopes: tuple[str, ...] = ("build_lens",)
                   ) -> M.Consent | None:
    return db.execute(select(M.Consent).where(M.Consent.project_id == project_id, M.Consent.person_id == person_id,
                                              M.Consent.scope.in_(scopes), M.Consent.revoked_at.is_(None))
                      .order_by(M.Consent.granted_at.desc())).scalars().first()


def grant(db: Session, project_id: str, person_id: str, scope: str, granted_by: str, *, synthetic: bool = False
          ) -> M.Consent:
    c = M.Consent(id=new_id("cns"), person_id=person_id, project_id=project_id, scope=scope, granted_by=granted_by,
                  text_version="1", synthetic=synthetic)
    db.add(c)
    R.audit(db, granted_by, "consent_granted", "person", person_id, {"scope": scope, "synthetic": synthetic})
    return c


def set_status(db: Session, lens: M.Lens, status: str, actor: str) -> None:
    lens.status = status
    R.audit(db, actor, {"paused": "lens_paused", "active": "lens_resumed"}.get(status, status), "lens", lens.id, {})


def revoke(db: Session, lens: M.Lens, actor: str) -> dict[str, int]:
    """Delete versions, items, digests and feedback-derived samples; keep an audit tombstone (FR-GOV-3)."""
    versions = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id)).scalars().all()
    vids = [v.id for v in versions]
    items = db.execute(select(M.LensItemRow.id).where(M.LensItemRow.lens_version_id.in_(vids))).scalars().all()
    counts = {"versions": len(vids), "items": len(items)}
    db.execute(delete(M.LensItemEvidence).where(M.LensItemEvidence.lens_item_id.in_(items)))
    db.execute(delete(M.BiasCheck).where(M.BiasCheck.lens_item_id.in_(items)))
    db.execute(delete(M.EdgeMapCell).where(M.EdgeMapCell.lens_version_id.in_(vids)))
    db.execute(delete(M.LensItemRow).where(M.LensItemRow.lens_version_id.in_(vids)))
    db.execute(delete(M.FindingRow).where(M.FindingRow.lens_version_id.in_(vids)))
    db.execute(delete(M.GrowthSnapshot).where(M.GrowthSnapshot.lens_id == lens.id))
    n = db.execute(delete(M.ResidualSample).where(M.ResidualSample.person_id == lens.person_id,
                                                  M.ResidualSample.evidence != "review")).rowcount
    counts["feedback_samples"] = int(n or 0)
    db.execute(delete(M.LensVersion).where(M.LensVersion.lens_id == lens.id))
    now = datetime.now(UTC)
    for c in db.execute(select(M.Consent).where(M.Consent.person_id == lens.person_id,
                                                M.Consent.project_id == lens.project_id,
                                                M.Consent.revoked_at.is_(None))).scalars():
        c.revoked_at = now
    lens.status = "revoked"
    R.audit(db, actor, "lens_revoked", "lens", lens.id, {"tombstone": {"person_id": lens.person_id,
                                                                       "revoked_at": now.isoformat(), **counts}})
    return counts

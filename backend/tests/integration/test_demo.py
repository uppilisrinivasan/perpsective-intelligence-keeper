"""Behaviour on the demo world (loaded with its committed snapshot)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from keeper.db import models as M
from keeper.db.session import session_scope


def test_consent_required_for_lens(demo):
    import asyncio

    from keeper.core.errors import ConsentRequired
    from keeper.lens.build import build_lens_version
    from keeper.llm.gateway import get_gateway
    with session_scope() as db:
        p = db.get(M.Project, demo)
        pe = db.execute(select(M.Person).where(M.Person.project_id == p.id, M.Person.role == "contributor")
                        ).scalars().first()
        ruler = db.execute(select(M.Ruler)).scalars().first()
        with pytest.raises(ConsentRequired):
            asyncio.run(build_lens_version(db, p, pe, cutoff=p.demo_now, ruler=ruler, reason="initial_build",
                                           gateway=get_gateway()))
        db.rollback()


def test_ruler_mismatch_rejected(demo):
    import asyncio

    from keeper.core.errors import RulerMismatch
    from keeper.fidelity.run import run_fidelity
    from keeper.llm.gateway import get_gateway
    with session_scope() as db:
        p = db.get(M.Project, demo)
        lv = db.execute(select(M.LensVersion)).scalars().first()
        pe = db.get(M.Person, p.primary_maintainer_id)
        other = M.Ruler(id="rul_other", spec={"llm": {"model_id": "x"}})
        with pytest.raises(RulerMismatch):
            asyncio.run(run_fidelity(db, p, pe, lv, other, gateway=get_gateway()))
        db.rollback()


def test_no_leakage_in_fidelity(demo):
    """Lens items used on held-out PRs were built only from reviews before the version's cutoff."""
    with session_scope() as db:
        for run in db.execute(select(M.FidelityRun)).scalars():
            lv = db.get(M.LensVersion, run.lens_version_id)
            item_ids = [i for (i,) in db.execute(select(M.LensItemRow.id).where(M.LensItemRow.lens_version_id == lv.id))]
            for ev in db.execute(select(M.LensItemEvidence).where(M.LensItemEvidence.lens_item_id.in_(item_ids),
                                                                  M.LensItemEvidence.finding_id.is_not(None))).scalars():
                f = db.get(M.FindingRow, ev.finding_id)
                if f is not None and f.created_at is not None:
                    assert f.created_at <= lv.cutoff_at, (f.id, f.created_at, lv.cutoff_at)
            for c in db.execute(select(M.FidelityCase).where(M.FidelityCase.run_id == run.id)).scalars():
                pr = db.execute(select(M.Pull).where(M.Pull.project_id == run.project_id,
                                                     M.Pull.number == c.pr_number)).scalars().one()
                assert pr.created_at >= lv.cutoff_at


def test_edge_map_ranks_planted_areas_first(demo):
    from keeper.eval import harness
    with session_scope() as db:
        r = harness.edge_map(db, db.get(M.Project, demo))
    assert r["measured"] and r["planted_in_top4"] >= 1, r


def test_revoke_deletes_lens_data(demo):
    from keeper.lens import governance as GOV
    with session_scope() as db:
        lens = db.execute(select(M.Lens).join(M.Person, M.Person.id == M.Lens.person_id)
                          .where(M.Person.role != "maintainer")).scalars().first()
        if lens is None:
            pytest.skip("no secondary lens in the snapshot")
        counts = GOV.revoke(db, lens, "maintainer")
        assert counts["versions"] >= 1
        assert db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id)).first() is None
        assert lens.status == "revoked"
        assert db.execute(select(M.AuditEvent).where(M.AuditEvent.object_id == lens.id,
                                                     M.AuditEvent.action == "lens_revoked")).first() is not None
        db.rollback()


def test_mirror_validates_against_github_schemas(root):
    from keeper.datagen import validate as VAL
    fn = getattr(VAL, "v1_schemas", None) or getattr(VAL, "check_schemas", None)
    if fn is None:
        pytest.skip("schema check is part of `python -m keeper.datagen validate`")
    assert not fn(root / "data")

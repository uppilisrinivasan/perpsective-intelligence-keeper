"""Projects and people (docs/05-api/02 §3)."""

from __future__ import annotations

import re

from sqlalchemy import func, select

from keeper.app import schemas as S
from keeper.app.deps import Ctx
from keeper.config import get_settings
from keeper.core.errors import Forbidden, NotFound, ValidationFailed
from keeper.db import models as M
from keeper.db.session import session_scope
from keeper.lens.governance import active_consent, grant
from keeper.services.common import job_ref, lens_of, person_ref, project
from keeper.sources import git as G


def _summary(db, p: M.Project) -> S.ProjectSummary:  # type: ignore[no-untyped-def]
    pulls = db.execute(select(func.count(M.Pull.id)).where(M.Pull.project_id == p.id)).scalar_one()
    open_ = db.execute(select(func.count(M.Pull.id)).where(M.Pull.project_id == p.id, M.Pull.state == "open")).scalar_one()
    reviewers = db.execute(select(func.count(M.Person.id)).where(M.Person.project_id == p.id,
                                                                 M.Person.role.in_(["maintainer", "reviewer"]))).scalar_one()
    maint = db.get(M.Person, p.primary_maintainer_id) if p.primary_maintainer_id else None
    return S.ProjectSummary(id=p.id, owner=p.owner, repo=p.repo, kind=p.kind, fictional=p.fictional,
                            counts=S.ProjectCounts(pulls=pulls, open=open_, reviewers=reviewers),
                            primary_maintainer=person_ref(maint))


def list_projects() -> S.ProjectList:
    with session_scope() as db:
        return S.ProjectList(items=[_summary(db, p) for p in db.execute(select(M.Project).order_by(M.Project.created_at))
                                    .scalars()])


def get_project(pid: str) -> S.ProjectDetail:
    with session_scope() as db:
        p = project(db, pid)
        base = _summary(db, p)
        files = []
        if p.repo_path:
            names = set(G.ls_tree(p.repo_path, "HEAD"))
            files = [f for f in ("CODEOWNERS", ".github/CODEOWNERS", "MAINTAINERS.md", "CONTRIBUTING.md", "SECURITY.md")
                     if f in names]
        learner_login = (p.meta or {}).get("learner_login")
        learner = db.execute(select(M.Person).where(M.Person.project_id == p.id, M.Person.login == learner_login)
                             ).scalars().first() if learner_login else None
        lv = db.execute(select(M.LensVersion).join(M.Lens).where(M.Lens.project_id == p.id)
                        .order_by(M.LensVersion.created_at.desc())).scalars().first()
        return S.ProjectDetail(**base.model_dump(), demo_now=p.demo_now, policy_files=files,
                               ruler_id=lv.ruler_id if lv else None, learner=person_ref(learner), html_base=p.html_base)


def import_project(body: S.ImportRequest, ctx: Ctx) -> S.JobAccepted:
    s = get_settings()
    if not s.IMPORT_ALLOWED:
        raise Forbidden("Importing repositories is turned off on this deployment.")
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer role can import projects.")
    m = re.search(r"([A-Za-z0-9-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", body.repo_url.strip())
    if not m:
        raise ValidationFailed("Enter a repository as owner/repo or a GitHub URL.")
    if not body.consent_ack:
        raise ValidationFailed("Please acknowledge how Keeper uses review comments (authors' copyright, attribution).",
                               {"field": "consent_ack"})
    from keeper.jobs.runner import get_runner
    jid, existing = get_runner().submit("import", {"owner": m.group(1), "repo": m.group(2),
                                                   "maintainer_login": body.maintainer_login, "since": body.since,
                                                   "max_pulls": body.max_pulls},
                                        key=f"import:{m.group(1)}/{m.group(2)}")
    return job_ref(jid, "import", existing)


def delete_project(pid: str, ctx: Ctx) -> None:
    with session_scope() as db:
        p = project(db, pid)
        if p.kind == "demo":
            raise Forbidden("The demo project can't be deleted; use ./run.sh --reset to start over.")
        db.delete(p)


def _person_summary(db, p: M.Project, pe: M.Person) -> S.PersonSummary:  # type: ignore[no-untyped-def]
    lens = lens_of(db, p, pe.id)
    reviews = db.execute(select(func.count(M.Review.id)).where(M.Review.reviewer_id == pe.id)).scalar_one()
    comments = db.execute(select(func.count(M.ReviewComment.id)).where(M.ReviewComment.author_id == pe.id)).scalar_one()
    prs = db.execute(select(func.count(M.Pull.id)).where(M.Pull.author_id == pe.id)).scalar_one()
    return S.PersonSummary(id=pe.id, login=pe.login, display_name=pe.display_name, role=pe.role,
                           has_lens=lens is not None and lens.status != "revoked", lens_id=lens.id if lens else None,
                           lens_status=lens.status if lens else None, fictional=p.fictional,
                           stats=S.PersonStats(reviews=reviews, comments=comments, prs=prs))


def list_people(pid: str, role: str | None) -> S.PeopleList:
    with session_scope() as db:
        p = project(db, pid)
        q = select(M.Person).where(M.Person.project_id == p.id)
        if role:
            q = q.where(M.Person.role == role)
        people = db.execute(q).scalars().all()
        learner = (p.meta or {}).get("learner_login")
        order = {"maintainer": 0, "reviewer": 1, "contributor": 2, "bot": 3}
        people.sort(key=lambda x: (0 if x.id == p.primary_maintainer_id else 1, x.login != learner,
                                   order.get(x.role, 9), x.login))
        return S.PeopleList(items=[_person_summary(db, p, x) for x in people])


def get_person(pid: str, person_id: str) -> S.PersonDetail:
    with session_scope() as db:
        p = project(db, pid)
        pe = db.get(M.Person, person_id)
        if pe is None or pe.project_id != p.id:
            raise NotFound("Person not found.")
        cons = db.execute(select(M.Consent).where(M.Consent.person_id == pe.id)).scalars().all()
        return S.PersonDetail(**_person_summary(db, p, pe).model_dump(), consents=[
            S.ConsentInfo(id=c.id, scope=c.scope, granted_by=c.granted_by, granted_at=c.granted_at,
                          revoked_at=c.revoked_at, text_version=c.text_version, synthetic=c.synthetic) for c in cons])


def record_consent(pid: str, person_id: str, body: S.ConsentRequest, ctx: Ctx) -> S.PersonDetail:
    if ctx.role != "maintainer":
        raise Forbidden("Only the maintainer role can record consent.")
    with session_scope() as db:
        p = project(db, pid)
        pe = db.get(M.Person, person_id)
        if pe is None:
            raise NotFound("Person not found.")
        if body.scope == "build_lens" and (not body.attest or (body.typed_login or "").strip() != pe.login):
            raise ValidationFailed("Confirm that you are this maintainer, or have their permission, and type their login.")
        if active_consent(db, p.id, pe.id, (body.scope,)) is None:
            grant(db, p.id, pe.id, body.scope, ctx.role)
    return get_person(pid, person_id)

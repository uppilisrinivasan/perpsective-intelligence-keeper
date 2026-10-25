"""FR-DATA-1…5: load the committed demo project from data/ (manifest check, bundle, mirror, consents, snapshot)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.config import get_settings
from keeper.core.errors import KeeperError
from keeper.core.timeutil import parse_ts
from keeper.datagen.validate import verify_manifest
from keeper.db import models as M
from keeper.db import repo as R
from keeper.ingest import ingest
from keeper.ingest import snapshot as SNAP
from keeper.lens.governance import active_consent, grant
from keeper.sources import git as G
from keeper.sources.github.mirror import MirrorReader

DEMO_ID = "prj_demo"


class DataIntegrityError(KeeperError):
    code, http_status = "data_integrity", 500


def manifest(data_dir: Path | None = None) -> dict[str, Any]:
    d = data_dir or get_settings().data_dir
    return json.loads((d / "manifest.json").read_text())


def load_demo(db: Session, *, with_snapshot: bool = True, verify: bool = True, progress: Any = None) -> M.Project:
    s = get_settings()
    data = s.data_dir
    if verify:
        problems = verify_manifest(data)
        if problems:
            raise DataIntegrityError("The demo data doesn't match data/manifest.json: " + "; ".join(problems[:5]) +
                                     ". Run `git checkout -- data/` (and check .gitattributes).", {"problems": problems[:20]})
    m = manifest(data)
    p = m["project"]
    if progress:
        progress("repository")
    bundle = data / "sources" / "git" / f"{p['repo']}.bundle"
    repo_path = s.runtime_dir / "repos" / p["repo"]
    G.clone_bundle(bundle, repo_path)
    mirror = data / "sources" / "github" / p["owner"] / p["repo"]
    proj = db.get(M.Project, DEMO_ID)
    if proj is None:
        proj = M.Project(id=DEMO_ID, owner=p["owner"], repo=p["repo"], kind="demo", fictional=True)
        db.add(proj)
    proj.demo_now = parse_ts(m["demo_now"])
    proj.repo_path = str(repo_path)
    proj.mirror_path = str(mirror)
    proj.html_base = MirrorReader(mirror).meta.get("html_base")
    proj.meta = {"package": p["repo"], "description": p.get("description"), "learner_login": p.get("learner_login"),
                 "security_reviewer_login": p.get("security_reviewer_login"),
                 "primary_maintainer_login": p["primary_maintainer_login"], "cutoff_v1": m["splits"]["cutoff_v1"],
                 "live_queue": m.get("live_queue", []), "tour_hints": m.get("tour_hints", {}),
                 "manifest_sha": R.get_state(db, "manifest_sha")}
    db.flush()
    if progress:
        progress("mirror")
    ingest(db, proj, MirrorReader(mirror), repo_path, primary_maintainer_login=p["primary_maintainer_login"],
           demo_now=proj.demo_now, cutoff=parse_ts(m["splits"]["cutoff_v1"]))
    people = {x.login: x for x in db.execute(select(M.Person).where(M.Person.project_id == DEMO_ID)).scalars()}
    snap = data / "snapshots" / DEMO_ID
    if with_snapshot and (snap / "snapshot.json").exists():
        if progress:
            progress("snapshot")
        SNAP.load(db, snap)
        R.set_state(db, "snapshot", json.loads((snap / "snapshot.json").read_text()))
    # synthetic consent rows for the fictional maintainer and the security reviewer (FR-GOV-1)
    for login in (p["primary_maintainer_login"], p.get("security_reviewer_login")):
        if login and login in people and active_consent(db, DEMO_ID, people[login].id) is None:
            grant(db, DEMO_ID, people[login].id, "build_lens", "demo-generator", synthetic=True)
            grant(db, DEMO_ID, people[login].id, "share_in_project", "demo-generator", synthetic=True)
    import hashlib
    R.set_state(db, "manifest_sha", hashlib.sha256((data / "manifest.json").read_bytes()).hexdigest())
    db.flush()
    return proj

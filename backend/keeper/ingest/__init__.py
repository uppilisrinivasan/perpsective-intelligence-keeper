"""L1 Ingest: a GitHub mirror (generated or imported) plus the git repository into the source tables.

Idempotent: re-running replaces the project's source rows (natural keys are GitHub IDs). docs/03-data/09 §1.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.core.timeutil import add_months, parse_ts
from keeper.db import models as M
from keeper.ids import stable_id
from keeper.sources import git as G
from keeper.sources import repo_files
from keeper.sources.github.mirror import MirrorReader

SOURCE_TABLES = [M.PullFile, M.Review, M.ReviewComment]


def _pid(project_id: str, gh_id: int) -> str:
    return stable_id("per", project_id, gh_id)


def wipe_sources(db: Session, project_id: str) -> None:
    pulls = select(M.Pull.id).where(M.Pull.project_id == project_id)
    for t in (M.PullFile, M.Review, M.ReviewComment):
        db.execute(delete(t).where(t.pull_id.in_(pulls)))
    for t in (M.Pull, M.IssueComment, M.Issue, M.TimelineEvent, M.Commit, M.CheckRun, M.Person):
        db.execute(delete(t).where(t.project_id == project_id))


def ingest(db: Session, project: M.Project, reader: MirrorReader, repo_path: Path,
           primary_maintainer_login: str | None = None, demo_now: datetime | None = None,
           cutoff: datetime | None = None) -> dict[str, int]:
    pid = project.id
    wipe_sources(db, pid)
    people: dict[int, dict[str, Any]] = {}
    names: dict[str, str] = {}

    def person(u: dict[str, Any] | None, at: str | None = None) -> str | None:
        if not u:
            return None
        gid = int(u["id"])
        p = people.setdefault(gid, {"login": u["login"], "type": u.get("type", "User"), "first": at})
        if at and (p["first"] is None or at < p["first"]):
            p["first"] = at
        return _pid(pid, gid)

    counts = {"pulls": 0, "files": 0, "reviews": 0, "review_comments": 0, "issue_comments": 0, "issues": 0,
              "events": 0, "commits": 0, "check_runs": 0}
    pr_commit_numbers: dict[str, list[int]] = {}
    for p in reader.iter_pulls():
        n = p["number"]
        pull_id = stable_id("pul", pid, n)
        author = person(p["user"], p["created_at"])
        db.add(M.Pull(id=pull_id, project_id=pid, number=n, gh_id=p["id"], title=p["title"], body=p.get("body"),
                      state=p["state"], draft=bool(p.get("draft")), author_id=author,
                      author_association=p.get("author_association"), created_at=parse_ts(p["created_at"]),
                      updated_at=parse_ts(p.get("updated_at")), closed_at=parse_ts(p.get("closed_at")),
                      merged_at=parse_ts(p.get("merged_at")), merged_by_id=person(p.get("merged_by")),
                      merge_commit_sha=p.get("merge_commit_sha") if p.get("merged") else None,
                      head_sha=p["head"]["sha"], head_ref=p["head"]["ref"], base_sha=p["base"]["sha"],
                      base_ref=p["base"]["ref"], labels=[lb["name"] for lb in p.get("labels", [])],
                      additions=p.get("additions", 0), deletions=p.get("deletions", 0),
                      changed_files=p.get("changed_files", 0), html_url=p.get("html_url"),
                      raw_path=f"pulls/{n}/pull.json"))
        counts["pulls"] += 1
        for f in reader.pull_files(n):
            binary = "patch" not in f and f["status"] != "removed" and f.get("changes", 0) == 0 or \
                ("patch" not in f and f["status"] in ("added", "modified"))
            db.add(M.PullFile(pull_id=pull_id, head_sha=p["head"]["sha"], filename=f["filename"],
                              previous_filename=f.get("previous_filename"), status=f["status"],
                              additions=f.get("additions", 0), deletions=f.get("deletions", 0),
                              patch=f.get("patch"), binary=bool(binary)))
            counts["files"] += 1
        for r in reader.reviews(n):
            db.add(M.Review(id=stable_id("rev", pid, r["id"]), pull_id=pull_id, gh_id=r["id"],
                            reviewer_id=person(r["user"], r.get("submitted_at")), state=r["state"], body=r.get("body"),
                            submitted_at=parse_ts(r.get("submitted_at")), commit_id=r.get("commit_id"),
                            author_association=r.get("author_association"), html_url=r.get("html_url")))
            counts["reviews"] += 1
        for c in reader.review_comments(n):
            db.add(M.ReviewComment(id=stable_id("rcm", pid, c["id"]), pull_id=pull_id, gh_id=c["id"],
                                   review_gh_id=c.get("pull_request_review_id"),
                                   in_reply_to_gh_id=c.get("in_reply_to_id"),
                                   author_id=person(c["user"], c["created_at"]), path=c.get("path"),
                                   line=c.get("line"), start_line=c.get("start_line"), side=c.get("side"),
                                   start_side=c.get("start_side"), original_line=c.get("original_line"),
                                   subject_type=c.get("subject_type"), diff_hunk=c.get("diff_hunk"),
                                   body=c.get("body") or "", commit_id=c.get("commit_id"),
                                   created_at=parse_ts(c["created_at"]), html_url=c.get("html_url")))
            counts["review_comments"] += 1
        for c in reader.commits(n):
            pr_commit_numbers.setdefault(c["sha"], []).append(n)
            if c.get("author") and c["commit"].get("author", {}).get("name"):
                names.setdefault(c["author"]["login"], c["commit"]["author"]["name"])
            if c["sha"] not in counts:
                pass
        for cr in reader.check_runs(p["head"]["sha"]):
            db.add(M.CheckRun(id=stable_id("chk", pid, cr["id"]), project_id=pid, head_sha=cr["head_sha"],
                              name=cr["name"], status=cr["status"], conclusion=cr.get("conclusion"),
                              summary=(cr.get("output") or {}).get("summary"),
                              completed_at=parse_ts(cr.get("completed_at"))))
            counts["check_runs"] += 1
    for iss in reader.issues():
        n = iss["number"]
        is_pull = "pull_request" in iss
        if not is_pull:
            db.add(M.Issue(id=stable_id("iss", pid, n), project_id=pid, number=n, gh_id=iss["id"], title=iss["title"],
                           body=iss.get("body"), state=iss["state"], state_reason=iss.get("state_reason"),
                           author_id=person(iss["user"], iss["created_at"]),
                           labels=[lb["name"] for lb in iss.get("labels", [])], created_at=parse_ts(iss["created_at"]),
                           closed_at=parse_ts(iss.get("closed_at")), is_pull=False, html_url=iss.get("html_url")))
            counts["issues"] += 1
        for c in reader.issue_comments(n):
            db.add(M.IssueComment(id=stable_id("icm", pid, c["id"]), project_id=pid, issue_number=n, gh_id=c["id"],
                                  author_id=person(c["user"], c["created_at"]), body=c.get("body") or "",
                                  created_at=parse_ts(c["created_at"]), html_url=c.get("html_url")))
            counts["issue_comments"] += 1
        for k, ev in enumerate(reader.timeline(n)):
            kind = ev.get("event", "")
            actor = person(ev.get("actor") or ev.get("user"))
            src = None
            if kind == "cross-referenced":
                src = ev.get("source", {}).get("issue", {}).get("number")
            at = ev.get("created_at") or ev.get("submitted_at") or (ev.get("committer") or {}).get("date")
            db.add(M.TimelineEvent(id=stable_id("tle", pid, n, k, kind), project_id=pid, issue_number=n, event=kind,
                                   actor_id=actor, created_at=parse_ts(at), commit_id=ev.get("commit_id") or ev.get("sha"),
                                   source_issue_number=src,
                                   payload={k2: ev.get(k2) for k2 in ("state", "label", "requested_reviewer",
                                                                      "state_reason") if ev.get(k2) is not None}))
            counts["events"] += 1
    # commits: the default branch and every PR head, from git
    seen: set[str] = set()
    log = G.git(repo_path, "log", "--all", "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%ce%x1f%cI%x1f%P%x1f%B%x1e")
    for rec in log.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, an, ae, ad, cn, ce, cd, parents, msg = rec.split("\x1f", 8)
        if sha in seen:
            continue
        seen.add(sha)
        db.add(M.Commit(sha=sha, project_id=pid, author_login=_login_from_email(ae), committer_login=_login_from_email(ce),
                        authored_at=parse_ts(ad), committed_at=parse_ts(cd), message=msg.strip(),
                        parents=parents.split(), pull_numbers=pr_commit_numbers.get(sha, [])))
        counts["commits"] += 1
        login = _login_from_email(ae)
        if login:
            names.setdefault(login, an)
    # people and roles
    rules = repo_files.parse_codeowners(G.show(repo_path, "HEAD", ".github/CODEOWNERS") or
                                        G.show(repo_path, "HEAD", "CODEOWNERS"))
    maint_file = set(repo_files.parse_maintainers(G.show(repo_path, "HEAD", "MAINTAINERS.md")))
    star_owners = set(next((o for p, o in rules if p == "*"), []))
    db.flush()
    merges: dict[str, int] = {}
    reviews_by: dict[str, int] = {}
    for pr in db.execute(select(M.Pull).where(M.Pull.project_id == pid)).scalars():
        if pr.merged_by_id and pr.merged_by_id != pr.author_id:
            merges[pr.merged_by_id] = merges.get(pr.merged_by_id, 0) + 1
    for rv, author in db.execute(select(M.Review.reviewer_id, M.Pull.author_id).join(M.Pull, M.Review.pull_id == M.Pull.id)
                                 .where(M.Pull.project_id == pid)):
        if rv and rv != author:
            reviews_by[rv] = reviews_by.get(rv, 0) + 1
    cfg = get_config().ingest["people"]
    primary = None
    for gid, p in people.items():
        person_id = _pid(pid, gid)
        login = p["login"]
        if p["type"] == "Bot" or login.endswith("[bot]"):
            role = "bot"
        elif login in star_owners or merges.get(person_id, 0) >= cfg["maintainer_min_merges"]:
            role = "maintainer"
        elif login in maint_file or reviews_by.get(person_id, 0) >= cfg["reviewer_min_reviews"]:
            role = "reviewer"
        else:
            role = "contributor"
        if primary_maintainer_login and login == primary_maintainer_login:
            primary = person_id
            role = "maintainer"
        db.add(M.Person(id=person_id, project_id=pid, gh_id=gid, login=login, display_name=names.get(login),
                        type=p["type"], role=role, first_seen_at=parse_ts(p["first"])))
    project.primary_maintainer_id = primary or project.primary_maintainer_id
    db.flush()
    assign_splits(db, project, demo_now, cutoff)
    return counts


def _login_from_email(email: str) -> str | None:
    m = re.match(r"^\d+\+([^@]+)@users\.noreply\.", email or "")
    return m.group(1) if m else None


def assign_splits(db: Session, project: M.Project, demo_now: datetime | None, cutoff: datetime | None = None) -> None:
    months = int(get_config().fidelity["holdout"]["months"])
    now = demo_now or project.demo_now
    if now is None:
        last = db.execute(select(M.Pull.created_at).where(M.Pull.project_id == project.id)
                          .order_by(M.Pull.created_at.desc())).scalars().first()
        now = last
    if now is None:
        return
    cutoff = cutoff or add_months(now, -months)
    for pr in db.execute(select(M.Pull).where(M.Pull.project_id == project.id)).scalars():
        if pr.state == "open":
            pr.split = "live"
        elif pr.created_at >= cutoff and (pr.closed_at is None or pr.closed_at <= now):
            pr.split = "holdout"
        else:
            pr.split = "train"
    meta = dict(project.meta or {})
    meta["cutoff_v1"] = cutoff.isoformat()
    project.meta = meta

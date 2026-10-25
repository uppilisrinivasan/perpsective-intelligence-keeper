"""L2: what each person noticed, H(S), extracted from their review material (methodology 02).

One `extract_findings` call per (PR, person) with all their units, so the model can merge a concern said twice.
Anchors, substantive flags, severity floors and history references are applied by code afterwards.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.core.types import Anchor, Finding
from keeper.db import models as M
from keeper.db import repo as R
from keeper.findings.anchors import human_anchor
from keeper.ids import stable_id

_REF = re.compile(r"(?<![\w/])#(\d{1,6})\b")


def review_material(db: Session, project: M.Project, pr: M.Pull) -> dict[str, dict[str, Any]]:
    """person_id → units: threads (root + their comments), review bodies, conversation comments, rejection."""
    comments = db.execute(select(M.ReviewComment).where(M.ReviewComment.pull_id == pr.id)
                          .order_by(M.ReviewComment.created_at)).scalars().all()
    reviews = db.execute(select(M.Review).where(M.Review.pull_id == pr.id).order_by(M.Review.submitted_at)
                         ).scalars().all()
    convo = db.execute(select(M.IssueComment).where(M.IssueComment.project_id == project.id,
                                                    M.IssueComment.issue_number == pr.number)
                       .order_by(M.IssueComment.created_at)).scalars().all()
    events = db.execute(select(M.TimelineEvent).where(M.TimelineEvent.project_id == project.id,
                                                      M.TimelineEvent.issue_number == pr.number)).scalars().all()
    bots = {p.id for p in db.execute(select(M.Person).where(M.Person.project_id == project.id,
                                                            M.Person.role == "bot")).scalars()}
    by_gh = {c.gh_id: c for c in comments}
    review_state = {r.gh_id: r.state for r in reviews}
    out: dict[str, dict[str, Any]] = {}

    def unit(pid: str | None) -> dict[str, Any] | None:
        if pid is None or pid == pr.author_id or pid in bots:
            return None
        return out.setdefault(pid, {"threads": {}, "reviews": [], "conversation": [], "rejection": None,
                                    "states": {}, "first_review_commit": None, "first_at": None})

    for c in comments:
        u = unit(c.author_id)
        if u is None:
            continue
        root = c
        while root.in_reply_to_gh_id and root.in_reply_to_gh_id in by_gh:
            root = by_gh[root.in_reply_to_gh_id]
        t = u["threads"].setdefault(root.gh_id, {"root": root, "comments": []})
        t["comments"].append(c)
        u["states"][c.gh_id] = review_state.get(c.review_gh_id or -1)
        if u["first_at"] is None or c.created_at < u["first_at"]:
            u["first_at"] = c.created_at
    for r in reviews:
        u = unit(r.reviewer_id)
        if u is None:
            continue
        if u["first_review_commit"] is None and r.commit_id:
            u["first_review_commit"] = r.commit_id
        if r.body and r.body.strip():
            u["reviews"].append(r)
            if u["first_at"] is None or (r.submitted_at and r.submitted_at < u["first_at"]):
                u["first_at"] = r.submitted_at
    closed = next((e for e in events if e.event == "closed"), None)
    for c in convo:
        u = unit(c.author_id)
        if u is None:
            continue
        mins = int(get_config().ingest["people"]["rejection_window_minutes"])
        if closed and pr.merged_at is None and closed.actor_id == c.author_id and closed.created_at and \
                timedelta(0) <= closed.created_at - c.created_at <= timedelta(minutes=mins):
            u["rejection"] = c
        else:
            u["conversation"].append(c)
    # keep only people with something to extract (approvals without a word are shallow reviews)
    return {k: v for k, v in out.items() if v["threads"] or v["reviews"] or v["conversation"] or v["rejection"]}


def shallow_reviewers(db: Session, pr: M.Pull) -> set[str]:
    """People whose only activity was an approval with no comment (their R− samples get a lower weight)."""
    reviews = db.execute(select(M.Review).where(M.Review.pull_id == pr.id)).scalars().all()
    active = {c.author_id for c in db.execute(select(M.ReviewComment).where(M.ReviewComment.pull_id == pr.id)).scalars()}
    out = set()
    for r in reviews:
        if r.state == "APPROVED" and not (r.body or "").strip() and r.reviewer_id not in active:
            out.add(r.reviewer_id)
    return out


def _taxonomy_list() -> list[dict[str, str]]:
    tax = get_config().taxonomy["categories"]
    return [{"id": k, "description": v["description"]} for k, v in tax.items()]


async def extract_pr(db: Session, project: M.Project, pr: M.Pull, person: M.Person, u: dict[str, Any], *,
                     gateway: Any, job_id: str | None = None, origin: str = "live") -> list[Finding]:
    cfg = get_config()
    files = [f.filename for f in db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id)).scalars()]
    threads = []
    sim_units = []
    for _root_id, t in u["threads"].items():
        root = t["root"]
        threads.append({"path": root.path, "line": root.line or root.original_line, "side": root.side or "RIGHT",
                        "diff_hunk": (root.diff_hunk or "")[-1500:],
                        "comments": [{"id": c.gh_id, "body": c.body, "is_reply": c.in_reply_to_gh_id is not None}
                                     for c in t["comments"]]})
        for c in t["comments"]:
            sim_units.append({"kind": "comment", "id": c.gh_id, "body": c.body, "path": root.path,
                              "line": root.line or root.original_line, "reply": c.in_reply_to_gh_id is not None,
                              "hunk": root.diff_hunk})
    reviews = [{"id": r.gh_id, "state": r.state, "body": r.body} for r in u["reviews"]]
    sim_units += [{"kind": "review", "id": r["id"], "body": r["body"], "state": r["state"]} for r in reviews]
    convo = [{"id": c.gh_id, "body": c.body} for c in u["conversation"]]
    sim_units += [{"kind": "issue_comment", "id": c["id"], "body": c["body"]} for c in convo]
    rej = {"id": u["rejection"].gh_id, "body": u["rejection"].body} if u["rejection"] else None
    if rej:
        sim_units.append({"kind": "rejection", "id": rej["id"], "body": rej["body"]})
    inputs = {"pr": {"number": pr.number, "title": pr.title, "files": files[:60]},
              "person": {"login": person.login}, "threads": threads, "reviews": reviews, "conversation": convo,
              "rejection": rej, "taxonomy": _taxonomy_list(),
              "_sim": {"units": sim_units, "files": files, "categories": list(cfg.taxonomy["categories"])}}
    res = await gateway.call("extract_findings", inputs, job_id=job_id, feature="lens")
    comment_by = {c.gh_id: c for t in u["threads"].values() for c in t["comments"]}
    root_of = {c.gh_id: t["root"] for t in u["threads"].values() for c in t["comments"]}
    review_by = {r.gh_id: r for r in u["reviews"]}
    convo_by = {c.gh_id: c for c in u["conversation"]}
    if rej:
        convo_by[rej["id"]] = u["rejection"]
    numbers = {n for (n,) in db.execute(select(M.Pull.number).where(M.Pull.project_id == project.id))} | \
        {n for (n,) in db.execute(select(M.Issue.number).where(M.Issue.project_id == project.id))}
    out: list[Finding] = []
    for k, d in enumerate(res.data.get("findings", [])):
        ids = d.get("source_ids", {})
        cids = [i for i in ids.get("comment_ids", []) if i in comment_by]
        rids = [i for i in ids.get("review_ids", []) if i in review_by]
        iids = [i for i in ids.get("issue_comment_ids", []) if i in convo_by]
        if not (cids or rids or iids):
            continue
        texts = [comment_by[i].body for i in cids] + [review_by[i].body or "" for i in rids] + \
            [convo_by[i].body for i in iids]
        times = [comment_by[i].created_at for i in cids] + [review_by[i].submitted_at for i in rids if
                                                            review_by[i].submitted_at] + [convo_by[i].created_at for i in iids]
        if cids:
            root = root_of[cids[0]]
            anchor = human_anchor(root.path, root.line, root.start_line, root.side, root.original_line,
                                  root.subject_type)
        else:
            hint = d.get("anchor_hint") or {}
            anchor = Anchor(scope="line", path=hint["path"], start_line=hint["line"], end_line=hint["line"]) \
                if hint.get("path") in files and hint.get("line") else Anchor(scope="pr")
        category = d["category"] if d["category"] in cfg.taxonomy["categories"] else "question"
        substantive = cfg.substantive(category, bool(d.get("is_question_challenge")))
        severity = d.get("severity", "minor")
        states = [u["states"].get(i) for i in cids] + [review_by[i].state for i in rids]
        if "CHANGES_REQUESTED" in states and severity in ("minor", "nit") and substantive:
            severity = "major"
        kind = d.get("kind", "comment")
        if rej and rej["id"] in iids:
            kind, severity = "rejection", "blocker"
        refs = sorted({int(m) for t in texts for m in _REF.findall(t or "") if int(m) in numbers and int(m) != pr.number})
        f = Finding(id=stable_id("fnd", project.id, pr.number, person.id, k, ",".join(map(str, cids + rids + iids))),
                    project_id=project.id, pr_number=pr.number, head_sha=u.get("first_review_commit") or pr.head_sha,
                    source="human", person_id=person.id, anchor=anchor, category=category, severity=severity,
                    kind=kind, statement=d["statement"].strip(), rationale=d.get("rationale"),
                    suggestion=d.get("suggestion"), substantive=substantive,
                    refs={"comment_ids": cids, "review_ids": rids, "issue_comment_ids": iids, "history_refs": refs},
                    llm_call_id=res.call_id, created_at=min(t for t in times if t) if times else pr.created_at)
        out.append(f)
    return out


async def extract_all(db: Session, project: M.Project, *, gateway: Any, job: Any = None,
                      person_ids: set[str] | None = None, origin: str = "live") -> dict[str, int]:
    """Re-extract human findings for every PR with review material (cached per input by the gateway)."""
    pulls = db.execute(select(M.Pull).where(M.Pull.project_id == project.id).order_by(M.Pull.number)).scalars().all()
    people = {p.id: p for p in db.execute(select(M.Person).where(M.Person.project_id == project.id)).scalars()}
    db.execute(delete(M.FindingRow).where(M.FindingRow.project_id == project.id, M.FindingRow.source == "human",
                                          M.FindingRow.context == "history"))
    db.commit()
    n_pr = n_f = 0
    for i, pr in enumerate(pulls):
        mats = review_material(db, project, pr)
        for pid, u in mats.items():
            if person_ids is not None and pid not in person_ids:
                continue
            fs = await extract_pr(db, project, pr, people[pid], u, gateway=gateway,
                                  job_id=job.id if job else None)
            for f in fs:
                db.add(R.to_row(f, origin=origin, context="history"))
            n_f += len(fs)
        n_pr += 1
        if i % 20 == 0:
            db.commit()
        if job is not None and i % 10 == 0:
            await job.progress(i + 1, len(pulls), stage="findings")
    db.flush()
    return {"prs": n_pr, "findings": n_f}

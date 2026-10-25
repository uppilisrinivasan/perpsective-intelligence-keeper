"""L5: what reality said about each PR (methodology 09 §1), derived by code from the data, and the links from bad
outcomes to the findings that predicted them (line overlap ± window and a compatible category)."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keeper.analysis.context import parse_patch
from keeper.config import get_config
from keeper.core.types import Finding
from keeper.db import models as M
from keeper.ids import stable_id
from keeper.sources import git as G

_REVERTS = re.compile(r"This reverts commit ([0-9a-f]{40})")
_FIXES = re.compile(r"(?i)\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)")


def _blame_origins(repo: str, base: str, path: str, lines: list[int], pr_commits: set[str]) -> list[int]:
    """Of `lines` (old-side line numbers at base), those last changed by one of pr_commits; returns their
    line numbers in the introducing commit."""
    if not lines:
        return []
    out = G.git(repo, "blame", "--porcelain", base, "--", path, check=False)
    hits: list[int] = []
    want = set(lines)
    for ln in out.splitlines():
        parts = ln.split(" ")
        if len(parts) >= 3 and len(parts[0]) == 40 and parts[0] in pr_commits:
            try:
                orig, final = int(parts[1]), int(parts[2])
            except ValueError:
                continue
            if final in want:
                hits.append(orig)
    return hits


def derive_outcomes(db: Session, project: M.Project) -> dict[str, int]:
    cfg = get_config().ingest["outcomes"]
    pid = project.id
    db.execute(delete(M.OutcomeLink).where(M.OutcomeLink.outcome_id.in_(
        select(M.Outcome.id).where(M.Outcome.project_id == pid))))
    db.execute(delete(M.Outcome).where(M.Outcome.project_id == pid))
    pulls = db.execute(select(M.Pull).where(M.Pull.project_id == pid).order_by(M.Pull.number)).scalars().all()
    by_num = {p.number: p for p in pulls}
    issues = db.execute(select(M.Issue).where(M.Issue.project_id == pid)).scalars().all()
    events = db.execute(select(M.TimelineEvent).where(M.TimelineEvent.project_id == pid)).scalars().all()
    xref: dict[int, set[int]] = {}
    for e in events:
        if e.event == "cross-referenced" and e.source_issue_number:
            xref.setdefault(e.issue_number, set()).add(e.source_issue_number)
    commits = {c.sha: c for c in db.execute(select(M.Commit).where(M.Commit.project_id == pid)).scalars()}
    pr_commits: dict[int, set[str]] = {}
    for c in commits.values():
        for n in c.pull_numbers or []:
            pr_commits.setdefault(n, set()).add(c.sha)
    owner_repo = f"{project.owner}/{project.repo}"
    repo = project.repo_path
    counts: dict[str, int] = {}

    def add(pr: M.Pull, kind: str, at: Any, evidence: dict[str, Any]) -> None:
        db.add(M.Outcome(id=stable_id("out", pid, pr.number, kind, evidence.get("by", "")), project_id=pid,
                         pr_number=pr.number, kind=kind, at=at, evidence=evidence))
        counts[kind] = counts.get(kind, 0) + 1

    files_cache: dict[str, list[dict[str, Any]]] = {}

    def files_of(p: M.Pull) -> list[dict[str, Any]]:
        if p.id not in files_cache:
            files_cache[p.id] = [{"filename": f.filename, "patch": f.patch} for f in
                                 db.execute(select(M.PullFile).where(M.PullFile.pull_id == p.id)).scalars()]
        return files_cache[p.id]

    def touched_by(fix: M.Pull, culprit: M.Pull) -> dict[str, list[int]]:
        """Lines of `culprit` (in its own commits' numbering) that `fix` modified or removed."""
        if not repo or not fix.base_sha:
            return {}
        out: dict[str, list[int]] = {}
        culprit_files = {f["filename"] for f in files_of(culprit)}
        for f in files_of(fix):
            if f["filename"] not in culprit_files or not f["patch"]:
                continue
            _, removed, _, _ = parse_patch(f["patch"])
            hits = _blame_origins(repo, fix.base_sha, f["filename"], [ln for ln, _ in removed],
                                  pr_commits.get(culprit.number, set()))
            if hits:
                out[f["filename"]] = sorted(set(hits))
        return out

    def added_count(p: M.Pull) -> int:
        return sum(len(parse_patch(f["patch"])[0]) for f in files_of(p) if f["patch"])

    merged = [p for p in pulls if p.merged_at]
    for p in pulls:
        if p.merged_at:
            add(p, "merged", p.merged_at, {})
            ci = db.execute(select(M.CheckRun).where(M.CheckRun.project_id == pid,
                                                     M.CheckRun.head_sha == p.head_sha)).scalars().all()
            if any(c.conclusion == "failure" for c in ci):
                add(p, "ci_failed", p.merged_at, {"checks": [c.name for c in ci if c.conclusion == "failure"]})
        elif p.state == "closed":
            add(p, "closed_unmerged", p.closed_at, {})
    # reverts: GitHub's revert-button PRs, and `git revert` messages on the default branch
    for rv in merged:
        m = re.match(r'^Revert "', rv.title or "")
        target = None
        if m:
            mm = re.search(rf"Reverts {re.escape(owner_repo)}#(\d+)", rv.body or "")
            target = by_num.get(int(mm.group(1))) if mm else None
        if target is None:
            for sha in pr_commits.get(rv.number, set()):
                for s in _REVERTS.findall(commits[sha].message if sha in commits else ""):
                    target = next((p for p in merged if p.merge_commit_sha == s or s in pr_commits.get(p.number, set())),
                                  None)
                    if target:
                        break
        if target and target.merged_at and rv.merged_at and \
                rv.merged_at - target.merged_at <= timedelta(days=int(cfg["revert_window_days"])):
            touched = {f["filename"]: [ln for ln, _ in parse_patch(f["patch"])[0]] for f in files_of(target)
                       if f["patch"]}
            add(target, "reverted", rv.merged_at, {"by": rv.number, "revert_pr": rv.number, "touched": touched})
    # post-merge bugs
    bug_labels = set(cfg["bug_labels"])
    fixers: dict[int, list[M.Pull]] = {}
    for p in merged:
        for n in _FIXES.findall(p.body or ""):
            fixers.setdefault(int(n), []).append(p)
    for iss in issues:
        if not bug_labels & set(iss.labels or []):
            continue
        cited = {int(n) for n in re.findall(r"#(\d+)", iss.body or "")} | xref.get(iss.number, set()) & set(by_num)
        cands = [by_num[n] for n in cited if n in by_num and by_num[n].merged_at]
        for fix in fixers.get(iss.number, []):
            for culprit in merged:
                if culprit.number == fix.number or not culprit.merged_at or culprit.merged_at >= iss.created_at:
                    continue
                if (culprit.number in cited or touched_by(fix, culprit)) and culprit not in cands:
                    cands.append(culprit)
        for culprit in cands:
            if not culprit.merged_at or not (culprit.merged_at < iss.created_at <= culprit.merged_at +
                                             timedelta(days=int(cfg["bug_window_days"]))):
                continue
            fix = next(iter(fixers.get(iss.number, [])), None)
            touched = touched_by(fix, culprit) if fix else {}
            add(culprit, "post_merge_bug", iss.created_at, {"by": f"issue{iss.number}", "issue": iss.number,
                                                             "issue_title": iss.title,
                                                             "fix_pr": fix.number if fix else None,
                                                             "touched": touched})
    # follow-up fixes: a later merged PR rewriting ≥ 30% of this PR's added lines, titled like a fix
    rx = re.compile(cfg["follow_up_title_regex"])
    window = timedelta(days=int(cfg["follow_up_window_days"]))
    for later in merged:
        if not (rx.search(later.title or "") or rx.search(later.body or "")):
            continue
        for culprit in merged:
            if culprit.number == later.number or not culprit.merged_at or not later.merged_at:
                continue
            if not (culprit.merged_at < later.created_at <= culprit.merged_at + window):
                continue
            if not {f["filename"] for f in files_of(culprit)} & {f["filename"] for f in files_of(later)}:
                continue
            touched = touched_by(later, culprit)
            n = sum(len(v) for v in touched.values())
            if n and n / max(1, added_count(culprit)) >= float(cfg["follow_up_min_line_share"]):
                add(culprit, "follow_up_fix", later.merged_at, {"by": later.number, "fix_pr": later.number,
                                                                 "touched": touched})
    db.flush()
    return counts


def link(db: Session, project: M.Project, findings: list[Finding], window: int) -> int:
    """Link bad outcomes to the findings on the same PR by line overlap (or file/PR scope) and category."""
    compat = get_config().taxonomy["outcome_compat"]
    outs = db.execute(select(M.Outcome).where(M.Outcome.project_id == project.id,
                                              M.Outcome.kind.in_(list(compat)))).scalars().all()
    by_pr: dict[int, list[Finding]] = {}
    for f in findings:
        by_pr.setdefault(f.pr_number, []).append(f)
    n = 0
    existing = {(lk.outcome_id, lk.finding_id) for lk in db.execute(
        select(M.OutcomeLink).join(M.Outcome).where(M.Outcome.project_id == project.id)).scalars()}
    for o in outs:
        touched: dict[str, list[int]] = o.evidence.get("touched") or {}
        for f in by_pr.get(o.pr_number, []):
            if f.category not in compat.get(o.kind, []):
                continue
            a = f.anchor
            hit = None
            if a.path and a.path in touched:
                if a.scope != "line" or a.start_line is None:
                    hit = {"scope": a.scope, "path": a.path}
                else:
                    lo, hi = a.start_line - window, (a.end_line or a.start_line) + window
                    lines = [x for x in touched[a.path] if lo <= x <= hi]
                    if lines:
                        hit = {"path": a.path, "lines": lines[:10]}
            elif a.scope == "pr" and touched:
                hit = {"scope": "pr"}
            if hit and (o.id, f.id) not in existing:
                db.add(M.OutcomeLink(outcome_id=o.id, finding_id=f.id, overlap=hit))
                existing.add((o.id, f.id))
                n += 1
    db.flush()
    return n


def addressed(db: Session, project: M.Project, pr: M.Pull, f: Finding, window: int,
              _cache: dict[str, Any] = {}) -> bool:  # noqa: B006 (deliberate per-process cache)
    """A concern counts as addressed when the PR's later commits changed lines around its anchor (or, for
    PR-level findings, when the PR was updated after it). Only ignored concerns can test a prediction."""
    if not project.repo_path or not pr.merged_at:
        return False
    reviewed = f.head_sha or pr.head_sha
    if reviewed == pr.head_sha:
        return False
    key = f"{reviewed}..{pr.head_sha}"
    if key not in _cache:
        _cache[key] = {d["filename"]: parse_patch(d["patch"]) for d in G.diff_files(project.repo_path, reviewed,
                                                                                     pr.head_sha)}
    changes = _cache[key]
    a = f.anchor
    if a.scope == "pr" or not a.path:
        return bool(changes)
    if a.path not in changes:
        return False
    if a.scope != "line" or a.start_line is None:
        return True
    _, removed, _, _ = changes[a.path]
    lo, hi = a.start_line - window, (a.end_line or a.start_line) + window
    return any(lo <= ln <= hi for ln, _ in removed)

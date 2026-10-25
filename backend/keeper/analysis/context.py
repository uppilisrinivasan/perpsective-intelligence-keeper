"""A1: the PR context block (methodology 01 §1). The baseline and the lens review see exactly this text.

Not included, by code: the author's login and history, and any reviews or comments on the PR (that would leak H
into C and L). The `no_author` variant also drops the author association (triage and slop: guardrail G7).
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.config import get_config
from keeper.core.types import FileChange, PRContext
from keeper.db import models as M
from keeper.sources import git as G
from keeper.sources import repo_files

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch: str | None) -> tuple[list[tuple[int, str]], list[tuple[int, str]], list[tuple[int, int]],
                                              list[dict[str, Any]]]:
    """(added [(new_line, text)], removed [(old_line, text)], hunk ranges [(new_start, new_end)], hunks)."""
    added: list[tuple[int, str]] = []
    removed: list[tuple[int, str]] = []
    ranges: list[tuple[int, int]] = []
    hunks: list[dict[str, Any]] = []
    if not patch:
        return added, removed, ranges, hunks
    o = n = 0
    cur: dict[str, Any] | None = None
    for ln in patch.split("\n"):
        m = _HUNK.match(ln)
        if m:
            o, n = int(m.group(1)), int(m.group(3))
            cur = {"header": ln, "new_start": n, "lines": []}
            hunks.append(cur)
            ranges.append((n, n + max(0, int(m.group(4) or 1) - 1)))
            continue
        if cur is None:
            continue
        if ln.startswith("+"):
            added.append((n, ln[1:]))
            cur["lines"].append(("+", n, ln[1:]))
            n += 1
        elif ln.startswith("-"):
            removed.append((o, ln[1:]))
            cur["lines"].append(("-", o, ln[1:]))
            o += 1
        elif ln.startswith("\\"):
            continue
        else:
            cur["lines"].append((" ", n, ln[1:] if ln else ""))
            o += 1
            n += 1
    return added, removed, ranges, hunks


def render_file_diff(path: str, f: FileChange, hunks: list[dict[str, Any]]) -> list[str]:
    out = [f"File: {path} ({f.status}, +{f.additions} -{f.deletions})"]
    if f.binary:
        out.append("  [binary file, not shown]")
        return out
    for h in hunks:
        out.append(h["header"])
        for kind, line, text in h["lines"]:
            if kind == "+":
                out.append(f"L{line} +{text}")
            elif kind == "-":
                out.append(f"     -{text}")
            else:
                out.append(f"L{line}  {text}")
    return out


def _match_any(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], g) for g in globs)


def pr_files(db: Session, project: M.Project, pr: M.Pull, head_sha: str | None = None) -> list[FileChange]:
    """Files at the PR head (from the mirror), or at another head of the PR (computed from git)."""
    head = head_sha or pr.head_sha
    if head == pr.head_sha or not project.repo_path:
        rows = db.execute(select(M.PullFile).where(M.PullFile.pull_id == pr.id).order_by(M.PullFile.filename)
                          ).scalars().all()
        return [FileChange(path=f.filename, status=f.status, previous_path=f.previous_filename, patch=f.patch,
                           additions=f.additions, deletions=f.deletions, binary=f.binary) for f in rows]
    out = []
    for f in sorted(G.diff_files(project.repo_path, pr.base_sha or "main", head), key=lambda x: x["filename"]):
        out.append(FileChange(path=f["filename"], status=f["status"], previous_path=f["previous_filename"],
                              patch=f["patch"], additions=f["additions"], deletions=f["deletions"],
                              binary=bool(f["binary"])))
    return out


def build_context(db: Session, project: M.Project, pr: M.Pull, *, no_author: bool = False,
                  repo_path: Path | None = None, head_sha: str | None = None) -> tuple[PRContext, str]:
    cfg = get_config().context
    head = head_sha or pr.head_sha
    checks = db.execute(select(M.CheckRun).where(M.CheckRun.project_id == project.id,
                                                 M.CheckRun.head_sha == head)).scalars().all()
    fcs, added, removed, ranges, all_hunks = [], {}, {}, {}, {}
    for fc in pr_files(db, project, pr, head):
        fcs.append(fc)
        a, r, rg, hk = parse_patch(fc.patch)
        added[fc.path], removed[fc.path], ranges[fc.path], all_hunks[fc.path] = a, r, rg, hk
    body = _HTML_COMMENT.sub("", pr.body or "").strip()[: int(cfg["max_description_chars"])]
    notes = ""
    rp = repo_path or (Path(project.repo_path) if project.repo_path else None)
    if rp is not None and rp.exists():
        for name in cfg.get("repo_notes_files", []):
            text = G.show(rp, pr.base_sha or "HEAD", name)
            if text:
                notes = repo_files.review_notes(text, cfg.get("repo_notes_heading_regex", r"^#+\s*review"),
                                                int(cfg["max_repo_notes_chars"]))
                break
    # diff text, bounded: drop lock and generated files first, then truncate per file
    order = sorted(fcs, key=lambda f: (_match_any(f.path, cfg.get("lock_file_globs", []) +
                                                  cfg.get("generated_file_globs", [])), f.path))
    lines: list[str] = []
    max_lines = int(cfg["max_diff_lines"])
    for f in order:
        flines = render_file_diff(f.path, f, all_hunks[f.path])
        if len(lines) + len(flines) > max_lines:
            keep = max(0, max_lines - len(lines) - 1)
            if keep > 1:
                lines.extend(flines[:keep])
            lines.append(f"[… {len(flines) - keep} lines omitted from {f.path}]")
            continue
        lines.extend(flines)
    header = [f"Repository: {project.owner}/{project.repo}", f"Pull request #{pr.number}: {pr.title}",
              f"Labels: {', '.join(pr.labels or []) or 'none'}", f"Base branch: {pr.base_ref or 'main'}"]
    if not no_author:
        header.append(f"Author association: {pr.author_association or 'NONE'}")
    if pr.draft:
        header.append("Draft: yes")
    ci = [{"name": c.name, "conclusion": c.conclusion, "summary": c.summary} for c in checks]
    block = "\n".join(header) + "\n\nDescription:\n" + (body or "(no description)") + "\n\nFiles:\n" + "\n".join(
        f"- {f.path} ({f.status}, +{f.additions} -{f.deletions}{', binary' if f.binary else ''})" for f in fcs) + \
        "\n\nDiff:\n" + "\n".join(lines) + "\n\nCI at the head:\n" + ("\n".join(
            f"- {c['name']}: {c['conclusion']} ({c['summary']})" for c in ci) or "- none") + \
        (f"\n\nRepository notes ({cfg['repo_notes_files'][0]}):\n{notes}" if notes else "")
    ctx = PRContext(repo=f"{project.owner}/{project.repo}", number=pr.number, title=pr.title, labels=pr.labels or [],
                    base_ref=pr.base_ref or "main", author_association=None if no_author else pr.author_association,
                    draft=pr.draft, description=body, files=fcs, diff_text="\n".join(lines), ci=ci, repo_notes=notes,
                    created_at=pr.created_at, head_sha=head,
                    changed_lines=sum(f.additions + f.deletions for f in fcs), added_lines=added,
                    removed_lines=removed, hunks=ranges)
    return ctx, block


def hunk_excerpt(ctx: PRContext, path: str | None, line: int | None, n: int) -> str:
    """Up to n lines of the new-side diff around line (for match judging and exemplars)."""
    if not path or path not in ctx.added_lines:
        return ""
    f = next((x for x in ctx.files if x.path == path), None)
    if f is None or not f.patch:
        return ""
    _, _, _, hunks = parse_patch(f.patch)
    for h in hunks:
        rows = h["lines"]
        idx = [i for i, (_, ln, _) in enumerate(rows) if ln == line] if line else [0]
        if idx:
            i = idx[0]
            lo = max(0, i - n // 2)
            return "\n".join(("+" if k == "+" else ("-" if k == "-" else " ")) + t for k, _, t in rows[lo:lo + n])
    return ""

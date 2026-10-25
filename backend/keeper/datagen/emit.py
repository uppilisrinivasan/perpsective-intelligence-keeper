"""G7 and G8: emit the GitHub mirror, the git bundle and the CI artefacts from the ledger (docs/03-data/06 §2).

CI is real: pytest runs at every PR head in a worktree; only `timestamp` and `hostname` in the JUnit XML are
rewritten to fit the timeline. Every mirror file is validated against GitHub's extracted OpenAPI schemas (V1).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Any

import jsonschema
from defusedxml import ElementTree as ET

from keeper.core.timeutil import iso, parse_ts
from keeper.datagen.github_objects import GH
from keeper.datagen.world import World
from keeper.sources import git as G

PAGE = 100


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


class Validator:
    """V1: validate payloads against config/schemas/github/<component>.json."""

    def __init__(self, schema_dir: Path):
        self.v: dict[str, jsonschema.Draft202012Validator] = {}
        self.dir = schema_dir
        self.errors: list[str] = []
        self.count = 0

    def check(self, component: str, obj: Any, where: str) -> None:
        if component not in self.v:
            self.v[component] = jsonschema.Draft202012Validator(json.loads((self.dir / f"{component}.json").read_text()))
        self.count += 1
        for e in list(self.v[component].iter_errors(obj))[:3]:
            loc = "/".join(str(p) for p in e.path)
            self.errors.append(f"{where}: {component} {loc}: {e.message[:160]}")


# ---------------------------------------------------------------------------------------------------------- CI
def run_ci(repo: Path, ledger: dict[str, Any], out_dir: Path, *, workers: int = 6) -> dict[str, dict[str, Any]]:
    """Run pytest at every PR head and at main. Returns sha → {conclusion, passed, failed, errors, skipped, time}."""
    heads: list[str] = []
    for rec in ledger["prs"].values():
        if not rec.get("skipped"):
            heads.extend(rec["heads"])
    heads.append(ledger["main_sha"])
    heads = list(dict.fromkeys(heads))
    tmp = Path(tempfile.mkdtemp(prefix="keeper-ci-"))
    results: dict[str, dict[str, Any]] = {}
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(sha: str) -> tuple[str, dict[str, Any]]:
        wt = tmp / sha[:12]
        G.export_tree(repo, sha, wt)
        junit = wt / ".ci-junit.xml"
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                            f"--junitxml={junit}", "-o", "junit_family=xunit2"], cwd=wt, capture_output=True,
                           text=True, env=env, timeout=300)
        res = parse_junit(junit) if junit.exists() else {"tests": 0, "failures": 1, "errors": 1, "skipped": 0,
                                                         "time": 0.0}
        res["conclusion"] = "success" if r.returncode == 0 else "failure"
        res["output_tail"] = (r.stdout + r.stderr)[-1500:]
        if junit.exists():
            shutil.copyfile(junit, out_dir / f"{sha}.xml.raw")
        shutil.rmtree(wt, ignore_errors=True)
        return sha, res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for sha, res in ex.map(one, heads):
            results[sha] = res
    shutil.rmtree(tmp, ignore_errors=True)
    return results


def parse_junit(path: Path) -> dict[str, Any]:
    root = ET.parse(str(path)).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    a = suite.attrib if suite is not None else {}
    return {"tests": int(a.get("tests", 0)), "failures": int(a.get("failures", 0)), "errors": int(a.get("errors", 0)),
            "skipped": int(a.get("skipped", 0)), "time": float(a.get("time", 0.0))}


def finalize_junit(out_dir: Path, sha: str, when: str, host: int, keep: bool) -> None:
    raw = out_dir / f"{sha}.xml.raw"
    if not raw.exists():
        return
    if keep:
        text = raw.read_text(encoding="utf-8")
        text = re.sub(r'timestamp="[^"]*"', f'timestamp="{when.replace("Z", "+00:00")}"', text)
        text = re.sub(r'hostname="[^"]*"', f'hostname="ci-runner-{host}"', text)
        import gzip
        (out_dir / f"{sha}.xml.gz").write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    raw.unlink()


# ------------------------------------------------------------------------------------------------------ mirror
def emit_mirror(w: World, ledger: dict[str, Any], ci: dict[str, dict[str, Any]], data_dir: Path,
                repo: Path) -> dict[str, Any]:
    sim = w.scenario["github_sim"]
    proj = w.project
    owner, name = proj["owner"], proj["repo"]
    people = ledger["people"]
    root = data_dir / "sources" / "github" / owner / name
    if root.exists():
        shutil.rmtree(root)
    val = Validator(w.dir.parent / "schemas" / "github")
    prs = sorted((r for r in ledger["prs"].values() if not r.get("skipped")), key=lambda r: r["number"])
    issues = sorted(ledger["issues"].values(), key=lambda r: r["number"])
    org_id = 7_340_000 + w.seed % 10_000
    gh = GH(sim["api_base"], sim["html_base"], owner, name, people, proj["owner_display"], proj["description"],
            proj["license"], repo_id=640_000_000 + w.seed % 1_000_000,
            created_at=iso(parse_ts(ledger["commits"][ledger["initial_sha"]]["authored_at"])), owner_id=org_id)
    end = w.scenario["timeline"]["end"]
    gh.pushed_at = max(c["committed_at"] for c in ledger["commits"].values())
    gh.updated_at = end
    gh.open_issues = sum(1 for p in prs if p["state"] == "open") + sum(1 for i in issues if i["state"] == "open")
    gh.size = 900
    from keeper.datagen.execute import IdGen
    ids = IdGen(w.seed + 11)
    # labels
    label_names = sorted({lb for p in prs for lb in p["labels"]} | {lb for i in issues for lb in i["labels"]} |
                         {"bug", "enhancement", "documentation", "question", "regression"})
    label_ids = {n: ids.next("label") for n in label_names}
    labels = [gh.label(n, label_ids[n]) for n in label_names]
    for lb in labels:
        val.check("label", lb, "labels")
    dump(root / "labels.page-001.json", labels)
    repo_obj = gh.full_repository()
    val.check("full-repository", repo_obj, "repo.json")
    dump(root / "repo.json", repo_obj)

    tree_cache: dict[str, str] = {}

    def tree_of(sha: str) -> str:
        if sha not in tree_cache:
            tree_cache[sha] = G.git(repo, "rev-parse", f"{sha}^{{tree}}").strip()
        return tree_cache[sha]

    # gh ids for PRs and issues
    for p in prs:
        p["gh_id"] = ids.next("pr")
    for i in issues:
        i["gh_id"] = ids.next("issue")
    issue_objs: dict[int, dict[str, Any]] = {}
    pull_simple: list[dict[str, Any]] = []
    endpoints: dict[str, Any] = {}

    def last_activity(rec: dict[str, Any]) -> str:
        times = [rec["created_at"], rec.get("closed_at") or ""]
        times += [c["created_at"] for c in rec.get("comments", [])]
        times += [c["created_at"] for c in rec.get("issue_comments", [])]
        times += [r["submitted_at"] for r in rec.get("reviews", [])]
        times += [t.get("at", "") for t in rec.get("timeline", [])]
        return max(t for t in times if t)

    for p in prs:
        n = p["number"]
        lbls = [gh.label(x, label_ids[x]) for x in p["labels"]]
        upd = last_activity(p)
        pending = [k for k in p.get("requested_reviewers", []) if p["state"] == "open"]
        p["pending_reviewers"] = pending if p["state"] == "open" else []
        files_raw = G.diff_files(repo, p["base_sha"], p["head_sha"])
        for f in files_raw:
            f["blob_sha"] = G.blob_sha(repo, p["head_sha"], f["filename"]) if f["status"] != "removed" else None
        files = [gh.diff_entry(f, p["head_sha"]) for f in files_raw]
        for k, f in enumerate(files):
            val.check("diff-entry", f, f"pulls/{n}/files[{k}]")
        n_ic = len(p["issue_comments"])
        n_rc = len(p["comments"])
        simple = gh.pull_simple(p, lbls, upd)
        full = gh.pull_full(p, lbls, upd, files_raw, n_ic, n_rc)
        val.check("pull-request-simple", simple, f"pulls index #{n}")
        val.check("pull-request", full, f"pulls/{n}/pull.json")
        pull_simple.append(simple)
        d = root / "pulls" / str(n)
        dump(d / "pull.json", full)
        dump(d / "files.page-001.json", files)
        reviews = [gh.review(rv, n) for rv in sorted(p["reviews"], key=lambda r: r["submitted_at"])]
        for k, rv in enumerate(reviews):
            val.check("pull-request-review", rv, f"pulls/{n}/reviews[{k}]")
        dump(d / "reviews.page-001.json", reviews)
        comments = [gh.review_comment(c, n) for c in sorted(p["comments"], key=lambda c: c["created_at"])]
        for k, c in enumerate(comments):
            val.check("pull-request-review-comment", c, f"pulls/{n}/comments[{k}]")
        dump(d / "comments.page-001.json", comments)
        commits = [gh.commit(ledger["commits"][s], tree_of(s)) for s in p["commits"]]
        for k, c in enumerate(commits):
            val.check("commit", c, f"pulls/{n}/commits[{k}]")
        dump(d / "commits.page-001.json", commits)
        closer = next((t["actor"] for t in reversed(p["timeline"]) if t["event"] == "closed"), None)
        iss = gh.issue(n, p["gh_id"] + 1, p["title"], p["body"], p["author"], lbls,
                       "open" if p["state"] == "open" else "closed", p["created_at"], upd, p.get("closed_at"), n_ic,
                       closer, None if p["state"] == "open" else "completed", p["association"],
                       pull={"url": f"{gh.r}/pulls/{n}", "html_url": f"{gh.h}/pull/{n}", "diff_url": f"{gh.h}/pull/{n}.diff",
                             "patch_url": f"{gh.h}/pull/{n}.patch", "merged_at": p.get("merged_at")})
        issue_objs[n] = iss
        # check runs at every head
        for sha in p["heads"]:
            res = ci.get(sha)
            if res is None:
                continue
            c = ledger["commits"][sha]
            started = parse_ts(c["committed_at"]) + timedelta(minutes=1)
            done = started + timedelta(seconds=int(res["time"]) + 34)
            summary = f"{res['tests'] - res['failures'] - res['errors'] - res['skipped']} passed" + (
                f", {res['failures'] + res['errors']} failed" if res["failures"] + res["errors"] else "") + \
                f" in {res['time']:.2f}s"
            cr = gh.check_run(ids.next("check"), sha, "tests (3.12)", res["conclusion"], iso(started), iso(done),
                              summary, {"id": p["gh_id"], "number": n, "url": f"{gh.r}/pulls/{n}",
                                        "head": {"ref": p["head_ref"], "sha": sha,
                                                 "repo": {"id": gh.repo_id, "url": gh.r, "name": name}},
                                        "base": {"ref": "main", "sha": p["base_sha"],
                                                 "repo": {"id": gh.repo_id, "url": gh.r, "name": name}}})
            val.check("check-run", cr, f"commits/{sha[:8]}/check-runs")
            dump(root / "commits" / sha / "check-runs.json", {"total_count": 1, "check_runs": [cr]})
            res["completed_at"] = iso(done)
    for i in issues:
        n = i["number"]
        lbls = [gh.label(x, label_ids[x]) for x in i["labels"]]
        upd = max([i["created_at"], i.get("closed_at") or ""] + [c["created_at"] for c in i["comments"]])
        closer = "maintainer" if i["state"] == "closed" else None
        obj = gh.issue(n, i["gh_id"], i["title"], i["body"], i["author"], lbls, i["state"], i["created_at"], upd,
                       i.get("closed_at"), len(i["comments"]), closer, i.get("state_reason"),
                       "FIRST_TIME_CONTRIBUTOR" if i["author"].startswith("d:") else "CONTRIBUTOR")
        issue_objs[n] = obj
    for n, obj in issue_objs.items():
        val.check("issue", obj, f"issues index #{n}")
    # indexes (pages of 100, created ascending, as returned with sort=created&direction=asc)
    for k in range(0, max(1, len(pull_simple)), PAGE):
        dump(root / "pulls" / f"index.page-{k // PAGE + 1:03d}.json", pull_simple[k:k + PAGE])
    all_issues = [issue_objs[k] for k in sorted(issue_objs)]
    for k in range(0, max(1, len(all_issues)), PAGE):
        dump(root / "issues" / f"index.page-{k // PAGE + 1:03d}.json", all_issues[k:k + PAGE])
    # issue comments and timelines, for PRs and issues
    eids = IdGen(w.seed + 17)
    for p in prs:
        n = p["number"]
        ics = [gh.issue_comment(c, n, True) for c in sorted(p["issue_comments"], key=lambda c: c["created_at"])]
        for k, c in enumerate(ics):
            val.check("issue-comment", c, f"issues/{n}/comments[{k}]")
        dump(root / "issues" / str(n) / "comments.page-001.json", ics)
        tl = timeline_for(gh, p, ledger, issue_objs, eids, tree_of, is_pull=True)
        for k, ev in enumerate(tl):
            val.check("timeline-issue-events", ev, f"issues/{n}/timeline[{k}]")
        dump(root / "issues" / str(n) / "timeline.page-001.json", tl)
    for i in issues:
        n = i["number"]
        ics = [gh.issue_comment(c, n, False) for c in i["comments"]]
        dump(root / "issues" / str(n) / "comments.page-001.json", ics)
        tl = timeline_for(gh, i, ledger, issue_objs, eids, tree_of, is_pull=False)
        for k, ev in enumerate(tl):
            val.check("timeline-issue-events", ev, f"issues/{n}/timeline[{k}]")
        dump(root / "issues" / str(n) / "timeline.page-001.json", tl)
    for f in sorted(root.rglob("*.json")):
        rel = str(f.relative_to(root))
        endpoints[rel] = {"etag": None, "pages": 1}
    from keeper import __version__
    meta = {"api_version": "2022-11-28", "api_base": sim["api_base"], "html_base": sim["html_base"],
            "generated_by": f"keeper-datagen {__version__}", "generated_at": end, "owner": owner, "repo": name,
            "endpoints": {k: v for k, v in sorted(endpoints.items()) if "/" not in k or k.startswith(("pulls/index",
                                                                                                        "issues/index"))}}
    dump(root / "_mirror.json", meta)
    return {"validated": val.count, "errors": val.errors, "prs": len(prs), "issues": len(issues),
            "gh_ids": {p["key"]: p["gh_id"] for p in prs}, "issue_gh_ids": {i["key"]: i["gh_id"] for i in issues}}


def timeline_for(gh: GH, rec: dict[str, Any], ledger: dict[str, Any], issue_objs: dict[int, dict[str, Any]],
                 ids: Any, tree_of: Any, *, is_pull: bool) -> list[dict[str, Any]]:
    items: list[tuple[str, int, dict[str, Any]]] = []
    for t in rec.get("timeline", []):
        ev, at = t["event"], t["at"]
        if ev in ("closed", "merged", "reopened"):
            items.append((at, 2, gh.ev_state(ids.next("event"), ev, t["actor"], at, t.get("commit_id"),
                                             "completed" if ev == "closed" else None)))
        elif ev == "labeled":
            items.append((at, 1, gh.ev_labeled(ids.next("event"), t["actor"], at, t["label"])))
        elif ev == "review_requested":
            items.append((at, 1, gh.ev_review_requested(ids.next("event"), t["actor"], at, t["requested"])))
        elif ev == "committed" and is_pull:
            items.append((at, 0, gh.ev_committed(ledger["commits"][t["sha"]], tree_of(t["sha"]))))
        elif ev == "cross-referenced":
            src = issue_objs.get(t["source_issue"])
            if src is not None:
                items.append((at, 1, gh.ev_cross_referenced(t["actor"], at, src)))
    if is_pull:
        for rv in rec.get("reviews", []):
            if rv.get("body") or rv["state"] != "COMMENTED":
                items.append((rv["submitted_at"], 1, gh.ev_reviewed(rv, rec["number"])))
    for c in rec.get("issue_comments", rec.get("comments", []) if not is_pull else []):
        items.append((c["created_at"], 1, gh.ev_commented(c, rec["number"], is_pull)))
    items.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in items]


def make_bundle(repo: Path, ledger: dict[str, Any], data_dir: Path, name: str) -> Path:
    out = data_dir / "sources" / "git" / f"{name}.bundle"
    out.parent.mkdir(parents=True, exist_ok=True)
    # only main and refs/pull/*/head (the working branches b/* are not part of the published repository)
    for ref in G.git(repo, "for-each-ref", "--format=%(refname)", "refs/heads/b/").split():
        G.git(repo, "update-ref", "-d", ref)
    if out.exists():
        out.unlink()
    G.git(repo, "bundle", "create", str(out), "--branches", "--glob=refs/pull/*")
    return out

"""G9 validation (docs/03-data/06 §6) and G11 manifest. `python -m keeper.datagen validate [--deep]` re-runs the
checks on the committed data (V1–V8; V9 and the rates need the ledger and run during generation)."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from keeper.config import get_config, get_settings
from keeper.core.timeutil import parse_ts
from keeper.llm.redact import Redactor
from keeper.sources import git as G

BUDGET_MB = {"sources/github": 25, "sources/git": 4, "sources/ci": 3, "ground_truth": 2, "snapshots": 8}
TOTAL_MB = 35


def _read_pages(d: Path, stem: str) -> list[Any]:
    out: list[Any] = []
    for f in sorted(d.glob(f"{stem}.page-*.json")):
        out.extend(json.loads(f.read_text()))
    return out


def dir_mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6 if p.exists() else 0.0


# ---------------------------------------------------------------------------------------------- slot checks
class _Checks:
    """Deterministic per-slot detectors for V5, run on the file text at the PR head."""

    @staticmethod
    def include_without_containment(text: str, line: int) -> bool:
        return ("commonpath" not in text or "abspath" in text or "isabs(name)" in text) and "os.path.join" in text

    @staticmethod
    def regex_in_loop(text: str, line: int) -> bool:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.For | ast.While):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and \
                            isinstance(sub.func.value, ast.Name) and sub.func.value.id == "re":
                        return True
        return False

    @staticmethod
    def open_without_encoding(text: str, line: int) -> bool:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open" and \
                    not any(k.arg == "encoding" for k in node.keywords) and len(node.args) < 3:
                return True
        return False

    @staticmethod
    def public_function_without_docstring(text: str, line: int) -> bool:
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and ast.get_docstring(node) is None:
                return True
        return False

    @staticmethod
    def public_function_without_hints(text: str, line: int) -> bool:
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and (
                    node.returns is None or any(a.annotation is None for a in node.args.args + node.args.kwonlyargs)):
                return True
        return False

    @staticmethod
    def mutable_default_or_bare_except(text: str, line: int) -> bool:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef):
                for d in node.args.defaults + [x for x in node.args.kw_defaults if x is not None]:
                    if isinstance(d, ast.List | ast.Dict | ast.Set):
                        return True
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                return True
        return False

    @staticmethod
    def public_param_removed(text: str, line: int) -> bool:
        return "DeprecationWarning" not in text

    @staticmethod
    def no_test_file(text: str, line: int) -> bool:
        return True

    @staticmethod
    def runtime_dependency_added(text: str, line: int) -> bool:
        return bool(re.search(r'^dependencies = \[\s*"', text, re.M))

    @staticmethod
    def binary_without_checksum(text: str, line: int) -> bool:
        return True


def check_slot(checks: dict[str, Any], slot: str, text: str | None, line: int | None) -> bool | None:
    spec = checks.get(slot)
    if spec is None or text is None:
        return None
    if spec["kind"] == "regex":
        return re.search(spec["pattern"], text) is not None
    if spec["kind"] == "ast":
        try:
            return bool(getattr(_Checks, spec["check"])(text, line or 0))
        except SyntaxError:
            return False
    return None


# -------------------------------------------------------------------------------------------------- validate
def validate(data_dir: Path, *, deep: bool = False, ledger: dict[str, Any] | None = None,
             plan: dict[str, Any] | None = None, scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {"checks": {}, "errors": [], "warnings": []}
    err, warn = report["errors"], report["warnings"]

    def done(name: str, ok: bool, detail: Any = None) -> None:
        report["checks"][name] = {"ok": ok, "detail": detail}

    gh_root = next((p for p in (data_dir / "sources" / "github").glob("*/*") if p.is_dir()), None)
    if gh_root is None:
        err.append("no GitHub mirror under data/sources/github")
        return report
    bundle = next((data_dir / "sources" / "git").glob("*.bundle"), None)
    # V1 schemas
    from keeper.datagen.emit import Validator
    v = Validator(get_settings().config_dir / "schemas" / "github")
    v.check("full-repository", json.loads((gh_root / "repo.json").read_text()), "repo.json")
    pulls = _read_pages(gh_root / "pulls", "index")
    for p in pulls:
        v.check("pull-request-simple", p, f"pulls index #{p['number']}")
    users: set[int] = set()
    review_ids: dict[int, set[int]] = {}
    for p in pulls:
        n = p["number"]
        d = gh_root / "pulls" / str(n)
        full = json.loads((d / "pull.json").read_text())
        v.check("pull-request", full, f"pulls/{n}")
        users.add(full["user"]["id"])
        for name, comp in (("files", "diff-entry"), ("reviews", "pull-request-review"),
                           ("comments", "pull-request-review-comment"), ("commits", "commit")):
            for k, item in enumerate(_read_pages(d, name)):
                v.check(comp, item, f"pulls/{n}/{name}[{k}]")
                if name == "reviews":
                    review_ids.setdefault(n, set()).add(item["id"])
                    users.add(item["user"]["id"])
        for k, ev in enumerate(_read_pages(gh_root / "issues" / str(n), "timeline")):
            v.check("timeline-issue-events", ev, f"issues/{n}/timeline[{k}]")
    for iss in _read_pages(gh_root / "issues", "index"):
        v.check("issue", iss, f"issues index #{iss['number']}")
    for f in (gh_root / "commits").glob("*/check-runs.json"):
        for cr in json.loads(f.read_text())["check_runs"]:
            v.check("check-run", cr, str(f.relative_to(gh_root)))
    done("V1", not v.errors, {"validated": v.count, "errors": v.errors[:20]})
    err.extend(v.errors[:20])

    # V2 referential integrity
    v2: list[str] = []
    shas_needed: set[str] = set()
    for p in pulls:
        n = p["number"]
        d = gh_root / "pulls" / str(n)
        comments = _read_pages(d, "comments")
        ids = {c["id"] for c in comments}
        for c in comments:
            if c["pull_request_review_id"] not in review_ids.get(n, set()):
                v2.append(f"#{n} comment {c['id']}: review {c['pull_request_review_id']} missing")
            if c.get("in_reply_to_id") and c["in_reply_to_id"] not in ids:
                v2.append(f"#{n} comment {c['id']}: in_reply_to outside the PR")
        full = json.loads((d / "pull.json").read_text())
        shas_needed.add(full["head"]["sha"])
        if full.get("merge_commit_sha"):
            shas_needed.add(full["merge_commit_sha"])
    numbers = {p["number"] for p in pulls} | {i["number"] for i in _read_pages(gh_root / "issues", "index")}
    for f in (gh_root / "issues").glob("*/timeline.page-*.json"):
        for ev in json.loads(f.read_text()):
            if ev.get("event") == "cross-referenced" and ev["source"]["issue"]["number"] not in numbers:
                v2.append(f"{f.parent.name}: cross-reference to an unknown number")
    repo_tmp = None
    if bundle is not None:
        repo_tmp = Path(tempfile.mkdtemp(prefix="keeper-validate-")) / "repo"
        G.clone_bundle(bundle, repo_tmp)
        missing = [s for s in shas_needed if not G.git_ok(repo_tmp, "cat-file", "-e", f"{s}^{{commit}}")]
        v2.extend(f"sha {s[:10]} not in the bundle" for s in missing[:10])
    done("V2", not v2, v2[:20])
    err.extend(v2[:20])

    # V3 diff fidelity (all PRs with --deep, otherwise a sample)
    v3: list[str] = []
    sample = pulls if deep else pulls[:: max(1, len(pulls) // 25)]
    if repo_tmp is not None:
        for p in sample:
            n = p["number"]
            files = _read_pages(gh_root / "pulls" / str(n), "files")
            got = {f["filename"]: f for f in G.diff_files(repo_tmp, p["base"]["sha"], p["head"]["sha"])}
            for f in files:
                g = got.get(f["filename"])
                if g is None or g["additions"] != f["additions"] or g["deletions"] != f["deletions"] or \
                        g["patch"] != f.get("patch"):
                    v3.append(f"#{n} {f['filename']}: diff differs from git")
            orig_cache: dict[str, dict[str, Any]] = {}
            for c in _read_pages(gh_root / "pulls" / str(n), "comments"):
                if c.get("in_reply_to_id"):
                    continue
                oc = c["original_commit_id"]
                if oc not in orig_cache:
                    orig_cache[oc] = {f["filename"]: f for f in G.diff_files(repo_tmp, p["base"]["sha"], oc)}
                f = orig_cache[oc].get(c["path"])
                # GitHub's diff_hunk: from the hunk header through the commented line, at the comment's commit
                if f is None or not f.get("patch") or not f["patch"].startswith(c["diff_hunk"].split("\n")[0]) \
                        and ("\n" + c["diff_hunk"].split("\n")[0]) not in f["patch"] or \
                        c["diff_hunk"] not in f["patch"]:
                    v3.append(f"#{n} comment {c['id']}: diff_hunk not from the file's patch")
    done("V3", not v3, {"checked_prs": len(sample), "problems": v3[:20]})
    err.extend(v3[:20])

    # V4 test reality: the final main passes; recorded conclusions match a re-run at sample heads
    v4: list[str] = []
    if repo_tmp is not None:
        heads = [p["head"]["sha"] for p in pulls]
        sample_heads = heads if deep else heads[:: max(1, len(heads) // 20)]
        for sha in [G.head(repo_tmp, "main")] + sample_heads:
            wt = repo_tmp.parent / f"wt-{sha[:8]}"
            G.export_tree(repo_tmp, sha, wt)
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=wt,
                               capture_output=True, text=True, timeout=300,
                               env={"PATH": "/usr/bin:/bin", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
                                    "HOME": str(wt), "PYTHONHASHSEED": "0"})
            got = "success" if r.returncode == 0 else "failure"
            f = gh_root / "commits" / sha / "check-runs.json"
            if sha == G.head(repo_tmp, "main"):
                if got != "success":
                    v4.append("pytest fails at the final main")
            elif f.exists():
                want = json.loads(f.read_text())["check_runs"][0]["conclusion"]
                if want != got:
                    v4.append(f"{sha[:8]}: recorded {want}, re-run {got}")
            dur = re.search(r"in ([0-9.]+)s", r.stdout)
            if dur and float(dur.group(1)) > float((scenario or {}).get("project", {}).get("size", {}).get(
                    "max_suite_seconds", 15)):
                v4.append(f"{sha[:8]}: suite took {dur.group(1)} s")
    done("V4", not v4, v4[:20])
    err.extend(v4[:20])

    # V5 slot validators (each planted slot is detectable at its location at the PR head)
    v5: list[str] = []
    gt = data_dir / "ground_truth" / "pr_slots.jsonl"
    checks = yaml.safe_load((get_settings().config_dir / "datagen" / "slot_checks.yaml").read_text())
    by_num = {p["number"]: p for p in pulls}
    n5 = 0
    if gt.exists() and repo_tmp is not None:
        for row in (json.loads(x) for x in gt.read_text().splitlines()):
            if row.get("eligible_only") or row["slot"] in ("X1", "T4") or not row["locations"]:
                continue
            p = by_num.get(row["pr_number"])
            if p is None:
                continue
            loc = row["locations"][0]
            text = G.show(repo_tmp, p["head"]["sha"] if not row["addressed"] else _first_head(gh_root, p), loc["path"])
            res = check_slot(checks, row["slot"], text, loc["line"])
            n5 += 1
            if res is False:
                v5.append(f"#{row['pr_number']} {row['slot']} not detectable in {loc['path']}")
    done("V5", not v5, {"checked": n5, "problems": v5[:20]})
    err.extend(v5[:20])

    # V6 timeline consistency
    v6: list[str] = []
    for p in pulls:
        full = json.loads((gh_root / "pulls" / str(p["number"]) / "pull.json").read_text())
        reviews = _read_pages(gh_root / "pulls" / str(p["number"]), "reviews")
        for rv in reviews:
            if rv["submitted_at"] < full["created_at"]:
                v6.append(f"#{p['number']}: review before the PR was opened")
            if full.get("merged_at") and rv["submitted_at"] > full["merged_at"]:
                v6.append(f"#{p['number']}: review after merge")
    done("V6", not v6, v6[:20])
    err.extend(v6[:20])

    # V7 rates (generation only: needs the plan)
    if plan is not None and ledger is not None and scenario is not None:
        v7 = rates(plan, scenario)
        done("V7", not v7["problems"], v7)
        warn.extend(v7["problems"])

    # V8 size and secret scan
    v8: list[str] = []
    for part, mb in BUDGET_MB.items():
        size = dir_mb(data_dir / part)
        if size > mb:
            v8.append(f"{part}: {size:.1f} MB over the {mb} MB budget")
    total = dir_mb(data_dir)
    if total > TOTAL_MB:
        v8.append(f"data/: {total:.1f} MB over the {TOTAL_MB} MB budget")
    red = Redactor({**get_config().redaction, "patterns": [p for p in get_config().redaction["patterns"]
                                                           if p["name"] not in ("email",)]})
    for f in data_dir.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".jsonl", ".xml", ".md", ".txt"):
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", text):
                if not m.group(1).endswith(".example") and m.group(1) != "localhost":
                    v8.append(f"{f.relative_to(data_dir)}: real e-mail domain {m.group(1)}")
                    break
            red(text[:200000])
            if any(k in red.hits for k in ("aws_access_key", "github_token", "github_fine_grained", "pem_block",
                                           "slack_token", "jwt")):
                v8.append(f"{f.relative_to(data_dir)}: secret-shaped string")
                red.hits.clear()
            if str(get_settings().path(".")) in text:
                v8.append(f"{f.relative_to(data_dir)}: contains a build-machine path")
    done("V8", not v8, {"total_mb": round(total, 2), "problems": v8[:20]})
    err.extend(v8[:20])

    # V9 ground-truth completeness: every human comment maps to a planted finding or a social/question comment
    ctf = data_dir / "ground_truth" / "comment_truth.jsonl"
    v9: list[str] = []
    if ctf.exists():
        known = {(r["comment_kind"], r["id"]) for r in (json.loads(x) for x in ctf.read_text().splitlines())}
        for p in pulls:
            d = gh_root / "pulls" / str(p["number"])
            for c in _read_pages(d, "comments"):
                if ("review_comment", c["id"]) not in known:
                    v9.append(f"#{p['number']} comment {c['id']} has no truth row")
            for rv in _read_pages(d, "reviews"):
                if rv["body"] and ("review", rv["id"]) not in known:
                    v9.append(f"#{p['number']} review {rv['id']} has no truth row")
    done("V9", not v9, v9[:20])
    err.extend(v9[:20])
    report["ok"] = not err
    return report


def _first_head(gh_root: Path, p: dict[str, Any]) -> str:
    commits = _read_pages(gh_root / "pulls" / str(p["number"]), "commits")
    return commits[0]["sha"] if commits else p["head"]["sha"]


def rates(plan: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    """V7: observed presence and flag rates against the planned rates (±50% relative), where n is large enough."""
    slots = {s["id"]: s for s in scenario["concern_slots"]}
    flags: dict[str, list[int]] = {}
    for p in plan["prs"]:
        if p["split"] == "live":
            continue
        flagged = set(p.get("extra", {}).get("flagged", []))
        reviewed_by_m = any(r.get("reviewer") == "maintainer" for r in p.get("rounds", []))
        start = parse_ts(plan["timeline"]["start"])
        month = (parse_ts(p["created_at"]) - start).days / 30.44
        for d in p["slots"]:
            s = slots[d["slot"]]
            if s.get("owner") != "maintainer" or not reviewed_by_m or "flag_rate" not in s:
                continue
            if month < float(s.get("starts_month", 0)):
                continue
            flags.setdefault(d["slot"], []).append(1 if d["slot"] in flagged else 0)
    out: dict[str, Any] = {"flag_rates": {}, "problems": []}
    for sid, xs in sorted(flags.items()):
        obs = sum(xs) / len(xs)
        want = float(slots[sid]["flag_rate"])
        out["flag_rates"][sid] = {"n": len(xs), "observed": round(obs, 2), "planned": want}
        if len(xs) >= 10 and want > 0.2 and abs(obs - want) / want > 0.5:
            out["problems"].append(f"{sid}: flag rate {obs:.2f} vs planned {want:.2f} (n={len(xs)})")
    return out


# -------------------------------------------------------------------------------------------------- manifest
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_manifest(data_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    files = {}
    for f in sorted(data_dir.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            files[str(f.relative_to(data_dir))] = sha256(f)
    manifest = {**meta, "files": files}
    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def verify_manifest(data_dir: Path) -> list[str]:
    """FR-DATA-2: every listed file exists with its hash (and nothing listed is missing)."""
    mf = data_dir / "manifest.json"
    if not mf.exists():
        return ["data/manifest.json is missing"]
    m = json.loads(mf.read_text())
    problems = []
    for rel, h in m.get("files", {}).items():
        f = data_dir / rel
        if not f.exists():
            problems.append(f"missing: {rel}")
        elif sha256(f) != h:
            problems.append(f"modified: {rel}")
    return problems

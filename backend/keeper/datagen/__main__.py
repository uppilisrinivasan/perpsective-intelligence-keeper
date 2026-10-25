"""python -m keeper.datagen run | validate [--deep] | snapshot | stats (docs/03-data/06 §9)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from keeper.config import get_settings


def _say(msg: str) -> None:
    print(msg, flush=True)


def cmd_run(a: argparse.Namespace) -> int:
    from keeper import __version__
    from keeper.datagen.emit import emit_mirror, finalize_junit, make_bundle, run_ci
    from keeper.datagen.execute import execute, save_ledger
    from keeper.datagen.plan import make_plan
    from keeper.datagen.truth import learner_notes, write_truth
    from keeper.datagen.validate import rates, validate, write_manifest
    from keeper.datagen.world import load_world

    s = get_settings()
    w = load_world(a.profile, a.seed)
    work = s.runtime_dir / "datagen" / "work"
    data = Path(a.out) if a.out else s.data_dir
    t0 = time.time()
    _say(f"G0  scenario {w.profile} (seed {w.seed})")
    _say("G1  world values: config/datagen/world.yaml (authored)")
    _say("G3  planning the timeline")
    plan = make_plan(w)
    _say(f"    {len(plan['prs'])} pull requests, {len(plan['issues'])} issues")
    _say("G2  initial repository · G4 history · G5 live queue (git)")
    ledger = execute(w, plan, work)
    save_ledger(ledger, work.parent / "ledger.json")
    (work.parent / "plan.json").write_text(json.dumps(plan, indent=1, default=str))
    _say(f"    {len(ledger['commits'])} commits, "
         f"{sum(len(r['comments']) for r in ledger['prs'].values())} review comments  ({time.time() - t0:.0f} s)")
    _say("G8  CI: pytest at every PR head")
    for sub in ("sources", "ground_truth", "generated"):
        if (data / sub).exists():
            shutil.rmtree(data / sub)
    junit_dir = data / "sources" / "ci" / "junit"
    ci = run_ci(work / "repo", ledger, junit_dir, workers=a.workers)
    fails = [sha for sha, r in ci.items() if r["conclusion"] != "success"]
    _say(f"    {len(ci)} heads, {len(fails)} failing  ({time.time() - t0:.0f} s)")
    _say("G7  GitHub mirror")
    rep = emit_mirror(w, ledger, ci, data, work / "repo")
    if rep["errors"]:
        _say(f"    ✗ {len(rep['errors'])} schema errors, first: {rep['errors'][0]}")
        return 1
    _say(f"    {rep['validated']} payloads valid against GitHub's schemas")
    final_heads = {r["heads"][-1] for r in ledger["prs"].values() if not r.get("skipped")} | {ledger["main_sha"]}
    for k, sha in enumerate(ci):
        when = ci[sha].get("completed_at") or ledger["commits"][sha]["committed_at"]
        finalize_junit(junit_dir, sha, when, 1 + k % 4, keep=sha in final_heads)
    make_bundle(work / "repo", ledger, data, w.project["repo"])
    _say("G6  demo learner notes · G10 ground truth")
    learner_notes(w, plan, ledger, data)
    write_truth(w, plan, ledger, data)
    _say("G9  validation")
    report = validate(data, deep=a.deep, ledger=ledger, plan=plan, scenario=w.scenario)
    report["rates"] = rates(plan, w.scenario)
    out = data / "generated"
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for name, c in sorted(report["checks"].items()):
        _say(f"    {'✓' if c['ok'] else '✗'} {name}")
    if report["errors"]:
        for e in report["errors"][:10]:
            _say(f"    ✗ {e}")
        return 1
    write_readme(data, w)
    _say("G11 manifest")
    write_manifest(data, manifest_meta(w, plan, ledger, __version__))
    _say(f"Done in {time.time() - t0:.0f} s. Next: python -m keeper.datagen snapshot")
    return 0


def manifest_meta(w: Any, plan: dict[str, Any], ledger: dict[str, Any], version: str) -> dict[str, Any]:
    people = plan["people"]
    prs = [r for r in ledger["prs"].values() if not r.get("skipped")]
    live = sorted(r["number"] for r in prs if r["split"] == "live")
    fix_demo = next((r["number"] for r in prs if r.get("live_key") and
                     next((p for p in plan["prs"] if p["key"] == r["key"]), {}).get("extra", {}).get("tour") == "fix_demo"),
                    None)
    return {
        "format_version": 1, "keeper_version": version,
        "scenario": {"path": "config/datagen/scenario.yaml", "sha256": w.sha256(), "seed": w.seed, "profile": w.profile},
        "demo_now": w.scenario["timeline"]["end"],
        "project": {"id": "prj_demo", "owner": w.project["owner"], "repo": w.project["repo"], "fictional": True,
                    "description": w.project["description"],
                    "primary_maintainer_login": people["maintainer"]["login"],
                    "security_reviewer_login": people["security"]["login"],
                    "learner_login": people["learner"]["login"]},
        "splits": {"cutoff_v1": plan["timeline"]["cutoff_v1"], "holdout_end": plan["timeline"]["end"]},
        "live_queue": live, "tour_hints": {"fix_demo": fix_demo},
        "models_used": {"datagen": "authored values (no model calls); structure by code, git and pytest"},
        "counts": {"pulls": len(prs), "reviews": sum(len(r["reviews"]) for r in prs),
                   "review_comments": sum(len(r["comments"]) for r in prs), "issues": len(ledger["issues"]),
                   "commits": len(ledger["commits"])},
    }


def write_readme(data: Path, w: Any) -> None:
    p = w.project
    (data / "README.md").write_text(f"""# Demo data (fictional)

This folder is the complete demo world for Keeper: a fictional open-source project, `{p['owner']}/{p['repo']}`,
with three years of history in exactly the shape of the GitHub REST API (v2022-11-28), its real git repository
(as a bundle) and real pytest results. Nobody in it is a real person; all hosts are `*.github.example`.

- `sources/`: what the real sources produce: the GitHub mirror, `git/{p['repo']}.bundle`, CI JUnit XML, and
  `keeper/practice_notes.json` (the demo learner's notes, as Keeper's own UI would store them).
- `ground_truth/`: what was planted, for evaluation only. Keeper's pipeline never reads it.
- `snapshots/`: Keeper's saved analysis of this project, used when no model API key is configured.
- `generated/`: validation and evaluation reports.

How it was made: `python -m keeper.datagen run` (seed {w.seed}, profile `{w.profile}`). The values (code, PR text,
review wording) are authored in `config/datagen/world.yaml` and the code templates; code produced every structural
field; git and pytest produced diffs, SHAs and test results. Released under the repository's licence (Apache-2.0).
""", encoding="utf-8")


def cmd_validate(a: argparse.Namespace) -> int:
    from keeper.datagen.validate import validate, verify_manifest

    data = get_settings().data_dir
    problems = verify_manifest(data)
    report = validate(data, deep=a.deep)
    for name, c in sorted(report["checks"].items()):
        print(f"{'✓' if c['ok'] else '✗'} {name}")
    for p in problems[:10]:
        print(f"✗ manifest: {p}")
    for e in report["errors"][:10]:
        print(f"✗ {e}")
    return 0 if report.get("ok") and not problems else 1


def cmd_stats(a: argparse.Namespace) -> int:
    from keeper.datagen.validate import dir_mb

    data = get_settings().data_dir
    m = json.loads((data / "manifest.json").read_text())
    print(json.dumps(m["counts"], indent=2))
    for part in ("sources/github", "sources/git", "sources/ci", "ground_truth", "snapshots"):
        print(f"{part:16} {dir_mb(data / part):6.2f} MB")
    return 0


def cmd_snapshot(a: argparse.Namespace) -> int:
    from keeper.datagen.snapshot import run_snapshot

    return run_snapshot(yes=a.yes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="keeper.datagen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--profile")
    r.add_argument("--seed", type=int)
    r.add_argument("--out")
    r.add_argument("--deep", action="store_true")
    r.add_argument("--workers", type=int, default=6)
    v = sub.add_parser("validate")
    v.add_argument("--deep", action="store_true")
    sub.add_parser("stats")
    sn = sub.add_parser("snapshot")
    sn.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)
    return {"run": cmd_run, "validate": cmd_validate, "stats": cmd_stats, "snapshot": cmd_snapshot}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

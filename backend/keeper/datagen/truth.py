"""G6 (demo learner notes) and G10 (ground truth). Written only to data/ground_truth/ and data/sources/keeper/;
the pipeline never reads ground_truth (import contract; FR-DATA-6)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from keeper.core.timeutil import parse_ts
from keeper.datagen.texts import choose, fill
from keeper.datagen.world import World

EDGE = {"E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "D1", "X1"}
SHARED = {"S1", "S2", "S3", "S4"}
BLIND = {"B1", "B2"}


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def expected_lane(pr: dict[str, Any], rec: dict[str, Any], plan_pr: dict[str, Any]) -> tuple[str, list[str]]:
    """The lane routing should give this PR, from its slots, under routing's rules (as if it were open)."""
    slots = {d["slot"] for d in plan_pr["slots"]}
    signals: list[str] = []
    kind = plan_pr["kind"]
    if kind == "build":
        ch = plan_pr["extra"].get("build", "")
        if "fixture" in ch:
            signals += ["binary_added_or_changed", "test_fixture_binary"]
        if ch.startswith("ci") or ch == "fixtures_fetch":
            signals.append("ci_workflow_changed")
        if ch.startswith("release") or ch.startswith("fixtures"):
            signals.append("build_script_changed")
        if "T1" in slots or "U1" in slots:
            signals.append("exec_or_network_in_code")
        return "unknown", signals
    if kind == "deps" and plan_pr["extra"].get("runtime"):
        signals.append("new_dependency")
    if plan_pr.get("expected_lane"):
        return plan_pr["expected_lane"], signals
    flagged = set(plan_pr.get("extra", {}).get("flagged", []))
    edge_present = slots & (EDGE - {"X1", "D1"})
    if "D1" in slots and parse_ts(plan_pr["created_at"]).month and "D1" in flagged:
        edge_present.add("D1")
    if edge_present:
        return "edge", signals
    if slots & BLIND:
        return "blind_spot", signals
    return "shared", signals


def write_truth(w: World, plan: dict[str, Any], ledger: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    gt = data_dir / "ground_truth"
    gt.mkdir(parents=True, exist_ok=True)
    people = plan["people"]
    login = {k: p["login"] for k, p in people.items()}
    num = ledger["number"]
    slots_def = {s["id"]: s for s in w.scenario["concern_slots"]}
    (gt / "slots.json").write_text(json.dumps(slots_def, indent=2, sort_keys=True) + "\n")
    plan_by_key = {p["key"]: p for p in plan["prs"]}
    pr_slots, lanes, outcomes = [], [], []
    for key, rec in sorted(ledger["prs"].items(), key=lambda kv: kv[1]["number"]):
        if rec.get("skipped"):
            continue
        pp = plan_by_key[key]
        flagged_by: dict[str, list[str]] = {}
        for r in pp.get("rounds", []):
            for f in r.get("findings", []):
                flagged_by.setdefault(f["planted"], []).append(login[r["reviewer"]])
        addressed = set(pp.get("extra", {}).get("addressed", []))
        out = pp.get("outcome")
        for d in pp["slots"]:
            loc = rec.get("slot_locations", {}).get(d["slot"], [None, None])
            o = None
            if out and out.get("cause_slot") == d["slot"]:
                o = {"kind": out["kind"], "fix_pr": num.get(out.get("fix_pr") or out.get("revert_pr") or "")}
            pr_slots.append({"pr_number": rec["number"], "slot": d["slot"], "variant": d.get("variant"),
                             "present": True, "eligible_only": bool(d.get("eligible")),
                             "locations": [{"path": loc[0], "line": loc[1]}] if loc[0] else [],
                             "flagged_by": sorted(set(flagged_by.get(d["slot"], []))),
                             "addressed": d["slot"] in addressed, "outcome": o})
        lane, sig = expected_lane(rec, rec, pp)
        handoff = None
        if pp.get("expected_handoff") == "security_reviewer" or lane == "unknown":
            handoff = login["security"]
        lanes.append({"pr_number": rec["number"], "split": rec["split"], "expected_lane": lane,
                      "expected_signals": sorted(set(sig)), "expected_handoff": handoff, "kind": pp["kind"],
                      "live_key": pp.get("live_key")})
        if rec.get("merged") or rec["state"] == "closed":
            outcomes.append({"pr_number": rec["number"], "outcome": "merged" if rec.get("merged") else "closed_unmerged",
                             "cause_slot": None, "base_rate": False})
        if out and rec.get("merged") and (out.get("fix_pr") or out.get("revert_pr")):
            outcomes.append({"pr_number": rec["number"], "outcome": out["kind"], "cause_slot": out.get("cause_slot"),
                             "base_rate": out.get("cause_slot") is None})
    _jsonl(gt / "pr_slots.jsonl", pr_slots)
    _jsonl(gt / "pr_lanes.jsonl", lanes)
    _jsonl(gt / "outcomes.jsonl", outcomes)
    ct = []
    for c in ledger["comment_truth"]:
        ct.append({**c, "author": login.get(c["author"], c["author"])})
    _jsonl(gt / "comment_truth.jsonl", ct)
    (gt / "plan.json").write_text(json.dumps(plan, indent=1, sort_keys=True, default=str) + "\n")
    import yaml

    from keeper.config import get_settings
    ev = yaml.safe_load((get_settings().config_dir / "eval.yaml").read_text())
    (gt / "eval_thresholds.json").write_text(json.dumps(ev, indent=2, sort_keys=True) + "\n")
    return {"pr_slots": len(pr_slots), "lanes": len(lanes), "comments": len(ct)}


def learner_notes(w: World, plan: dict[str, Any], ledger: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    """G6: the demo learner's notes for each candidate practice PR, at the planned skill per session kind."""
    rng = np.random.Generator(np.random.PCG64(w.seed + 61))
    cfg = w.scenario["learner_demo"]
    ph = w.world["phrases"]["learner_notes"]
    maint = "maintainer"
    plan_by_key = {p["key"]: p for p in plan["prs"]}
    truth_rows = []
    sessions: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for key, rec in ledger["prs"].items():
        if rec.get("skipped") or rec["split"] != "holdout" or not rec.get("merged"):
            continue
        pp = plan_by_key[key]
        mcomments = [c for c in rec["comments"] if c["author"] == maint and c.get("slot") and not c.get("in_reply_to")]
        if len(mcomments) < 1:
            continue
        for s in cfg["sessions"]:
            notes: list[dict[str, Any]] = []
            caught, own = [], []
            for c in mcomments:
                slot = c["slot"]
                typ = "edge" if slot in EDGE else ("blind_spot" if slot in BLIND else "shared")
                if rng.random() < float(s["skill"][typ]):
                    statement = re.split(r"(?<=[.!?])\s", c["body"].strip())[0][:160]
                    text = fill(choose(ph["catch_style"], key, s["kind"], c["id"]), fn=rec.get("fn") or "this",
                                statement=statement, statement_lc=statement[:1].lower() + statement[1:])
                    notes.append({"scope": "line", "path": c["path"], "line": c["original_line"], "text": text})
                    caught.append(slot)
            for d in pp["slots"]:
                if d["slot"] in BLIND and d["slot"] not in {c["slot"] for c in mcomments} and \
                        rng.random() < float(cfg["own_eye_rate"]) * 4:
                    loc = rec.get("slot_locations", {}).get(d["slot"])
                    if loc and loc[0]:
                        notes.append({"scope": "line", "path": loc[0], "line": loc[1],
                                      "text": "This opens the file without an explicit encoding, or leaves it open if "
                                              "it raises."})
                        own.append(d["slot"])
            if rng.random() < float(cfg["noise_rate"]):
                notes.append({"scope": "pr", "path": None, "line": None,
                              "text": fill(choose(ph["noise"], key, s["kind"]), fn=rec.get("fn") or "this")})
            sessions.setdefault(s["kind"], {})[str(rec["number"])] = notes
            truth_rows.append({"session": s["kind"], "item_pr": rec["number"], "planted_catches": caught,
                               "own_eye": own})
    out = data_dir / "sources" / "keeper"
    out.mkdir(parents=True, exist_ok=True)
    learner = plan["people"]["learner"]["login"]
    (out / "practice_notes.json").write_text(json.dumps({"learner": learner, "target": plan["people"][maint]["login"],
                                                         "sessions": sessions}, indent=1, sort_keys=True) + "\n")
    _jsonl(data_dir / "ground_truth" / "learner.jsonl", truth_rows)
    return {"items": len(truth_rows)}

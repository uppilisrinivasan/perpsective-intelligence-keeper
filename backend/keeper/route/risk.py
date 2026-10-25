"""Risk signals (methodology 07 §2), evaluated in code on every PR: the "unknown to both" detector.

Pure: the caller passes the PR context, the pyproject text before and after, and the coverage information.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from keeper.core.globs import area_of, match, match_any
from keeper.core.types import LensItem, PRContext, RiskSignal
from keeper.sources.repo_files import dep_name, pyproject_dependencies

_B64ISH = re.compile(r"[A-Za-z0-9+/=]{40,}|[0-9a-fA-F]{40,}")


def entropy(s: str) -> float:
    c = Counter(s)
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0


def _is_test(path: str) -> bool:
    return path.startswith("tests/") or "/tests/" in path or path.rsplit("/", 1)[-1].startswith("test_")


def new_dependencies(pyproject_base: str | None, pyproject_head: str | None, ctx: PRContext,
                     dependency_files: list[str]) -> list[dict[str, str | None]]:
    """Dependencies added in pyproject ([project] dependencies and optional dependencies) or requirements files."""
    out: list[dict[str, str | None]] = []
    if pyproject_head is not None and any(f.path == "pyproject.toml" for f in ctx.files):
        b, h = pyproject_dependencies(pyproject_base), pyproject_dependencies(pyproject_head)
        before = {dep_name(x)[0] for x in b["dependencies"]} | {dep_name(x)[0] for v in b["optional"].values() for x in v}
        for spec in h["dependencies"]:
            name, ver = dep_name(spec)
            if name not in before:
                out.append({"name": name, "version": ver, "spec": spec, "kind": "runtime"})
        for group, specs in h["optional"].items():
            for spec in specs:
                name, ver = dep_name(spec)
                if name not in before and group != "test":
                    out.append({"name": name, "version": ver, "spec": spec, "kind": f"optional:{group}"})
    for f in ctx.files:
        if f.path != "pyproject.toml" and match_any(f.path, dependency_files):
            for _, text in ctx.added_lines.get(f.path, []):
                t = text.strip()
                if t and not t.startswith("#") and not t.startswith("-"):
                    name, ver = dep_name(t)
                    out.append({"name": name, "version": ver, "spec": t, "kind": "runtime"})
    return out


def evaluate(ctx: PRContext, cfg: dict[str, Any], *, pyproject_base: str | None = None,
             pyproject_head: str | None = None, covering_items: list[LensItem] | None = None,
             person_area_findings: dict[str, int] | None = None, area_depth: int = 2) -> list[RiskSignal]:
    """Fire every configured signal on ctx; mark each covered when a validated edge item covers it."""
    sig = cfg["signals"]
    fired: list[RiskSignal] = []
    paths = [f.path for f in ctx.files] + [f.previous_path for f in ctx.files if f.previous_path]

    def add(key: str, ps: list[str], evidence: list[str] | None = None) -> None:
        s = sig[key]
        fired.append(RiskSignal(key=key, label=s.get("label", key), severity=s["severity"],
                                paths=sorted(set(ps)), evidence=evidence or []))

    # build scripts, CI, policy files
    bs = [p for p in paths if match_any(p, sig["build_script_changed"]["build_paths"])]
    if pyproject_head is not None and "pyproject.toml" in paths:
        b, h = pyproject_dependencies(pyproject_base), pyproject_dependencies(pyproject_head)
        if b["build_system"] != h["build_system"] or b.get("scripts") != h.get("scripts"):
            bs.append("pyproject.toml")
    if bs:
        add("build_script_changed", bs)
    ci = [p for p in paths if match_any(p, sig["ci_workflow_changed"]["paths"])]
    if ci:
        add("ci_workflow_changed", ci)
    pol = [p for p in paths if match_any(p, sig["permissions_or_policy_changed"]["paths"])]
    if pol:
        add("permissions_or_policy_changed", pol)
    # binaries
    exts = tuple(sig["binary_added_or_changed"]["binary_exts"])
    binaries = [f.path for f in ctx.files if f.status in ("added", "modified") and (f.binary or f.path.endswith(exts))]
    if binaries:
        add("binary_added_or_changed", binaries, [f"{p}" for p in binaries])
        fx = [p for p in binaries if match_any(p, sig["test_fixture_binary"]["paths"])]
        if fx:
            add("test_fixture_binary", fx)
    # dependencies
    deps = new_dependencies(pyproject_base, pyproject_head, ctx, cfg.get("dependency_files", []))
    if any(d["kind"] == "runtime" or str(d["kind"]).startswith("optional") for d in deps):
        add("new_dependency", [p for p in paths if match_any(p, cfg.get("dependency_files", []))],
            [f"{d['name']} {d['version'] or ''} ({d['kind']})".strip() for d in deps])
    src_changed = []
    for f in ctx.files:
        if match_any(f.path, cfg.get("dependency_files", [])) or f.path == "pyproject.toml":
            for _, t in ctx.added_lines.get(f.path, []):
                if re.search(r"--(extra-)?index-url|git\+https?://|--hash=|\[\[tool\.\w+\.source\]\]", t):
                    src_changed.append(f.path)
    if src_changed:
        add("dependency_source_changed", src_changed)
    # obfuscated content and exec/network calls on added lines
    ob = sig["obfuscated_content"]
    obf, exe = [], []
    pats = sig["exec_or_network_in_code"]["patterns"]
    for path, lines in ctx.added_lines.items():
        for ln, text in lines:
            for m in _B64ISH.finditer(text):
                run = m.group(0)
                if len(run) >= int(ob["entropy_min_len"]) and entropy(run) >= float(ob["entropy_min_bits"]):
                    obf.append(path)
            if not _is_test(path) and path.endswith(".py") and any(p in text for p in pats):
                exe.append(f"{path}:{ln}")
    if obf:
        add("obfuscated_content", obf)
    if exe:
        add("exec_or_network_in_code", [e.split(":")[0] for e in exe], exe[:5])
    # unfamiliar territory: many changed lines in areas the person has barely reviewed, and no item path triggers
    low = sig.get("low_lens_coverage")
    if low and person_area_findings is not None:
        lines_by_area: Counter[str] = Counter()
        for f in ctx.files:
            if not _is_test(f.path):
                lines_by_area[area_of(f.path, area_depth)] += f.additions + f.deletions
        item_paths = [g for it in (covering_items or []) for g in it.triggers.paths]
        unfamiliar = [a for a, n in lines_by_area.items()
                      if person_area_findings.get(a, 0) < int(low["coverage_min_findings"])
                      and not any(match(f.path, g) for f in ctx.files if area_of(f.path, area_depth) == a
                                  for g in item_paths)]
        if sum(lines_by_area[a] for a in unfamiliar) >= int(low["coverage_min_lines"]):
            add("low_lens_coverage", [f.path for f in ctx.files if area_of(f.path, area_depth) in unfamiliar])
    # coverage by validated edge items (this person's or another consenting lens in the project)
    for s in fired:
        cats = set(sig[s.key].get("covering_categories", []) or [])
        if not cats:
            continue
        for it in covering_items or []:
            if it.type != "edge" or it.status != "validated" or it.category not in cats:
                continue
            if any(match(p, g) for p in s.paths for g in it.triggers.paths):
                s.covered = True
                s.covered_by.append(it.id)
    return fired


def blocking(signals: list[RiskSignal]) -> bool:
    """The absolute rule (NFR-SAFE-2): any high or medium signal means the PR can never be `shared`."""
    return any(s.severity in ("high", "medium") for s in signals)


def uncovered(signals: list[RiskSignal]) -> list[RiskSignal]:
    return [s for s in signals if not s.covered]

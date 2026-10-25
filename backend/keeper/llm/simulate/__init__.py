"""The offline simulator behind `LLM_PROVIDER=fake`: one deterministic responder per prompt.

It reads only what the prompt itself shows (the `_sim` side channel carries the same PR context, items and notes
in structured form). It never reads ground truth. Its judgement is deliberately generic and imperfect:
- extraction classifies comments with a review-vocabulary lexicon;
- the generic review applies static-review heuristics with fixed catch rates (it cannot know a project's
  unwritten rules, so project-specific concerns are rarely caught);
- the lens review acts only on what the lens learned (triggers, code patterns, counter-patterns);
- fixes are pattern fixers that read test failures and repair.
Everything it produces is labelled "offline simulation" in the API and the UI, never as a Nemotron result.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from keeper.core.textsim import similarity, tokens

# ------------------------------------------------------------------------------------------------- helpers


def _h(*parts: object) -> float:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def _first_sentence(text: str, words: int = 30) -> str:
    t = re.sub(r"```.*?```", "", text or "", flags=re.S).strip()
    t = re.split(r"(?<=[.!?])\s+|\n\n", t)[0].strip()
    t = re.sub(r"^(please|could you|can you|nit:|nit)\s*,?\s*", "", t, flags=re.I).strip()
    if t:
        t = t[0].upper() + t[1:]
    ws = t.split()
    return " ".join(ws[:words]).rstrip(",;:") + ("" if len(ws) <= words else "…")


LEXICON: dict[str, list[tuple[str, float]]] = {
    "security": [(r"escap|travers|symlink|untrusted|don't control|confine", 2.0), (r"\broot\b", 1.0),
                 (r"secret|token|password|leak|ci logs|environment value|env value|echo the value", 2.0),
                 (r"depth limit|exhaust the stack|crafted|malicious|take the loader down|depth cap", 2.0),
                 (r"binary (blob|fixture)|checksum|sha256", 2.0), (r"realpath|commonpath", 1.0)],
    "invariant": [(r"round[- ]trip|dumps\(loads", 3.0), (r"preserve|reorder|key order|order of entries|don't sort", 2.0),
                  (r"laminaerror|line and (a )?column|error hierarchy|where in the file", 2.5)],
    "dependency": [(r"runtime dependenc|optional extra|vendor|no new runtime", 3.0)],
    "performance": [(r"hot path|per[- ]character|regex|milliseconds|overhead|tokenizer runs", 2.5)],
    "history_context": [(r"#\d+", 1.5), (r"revert|we had|is how we got|history|discussion on", 1.5)],
    "api_compat": [(r"deprecat|breaks every caller|public signature|on upgrade|keep .* working", 3.0)],
    "tests": [(r"\btests?\b", 1.5), (r"each branch|every branch|per branch", 1.0)],
    "docs": [(r"docstring|changelog|document", 2.5)],
    "style": [(r"\bnit\b|snake_case|naming|unused import|formatting", 2.5)],
    "correctness": [(r"mutable default|bare `?except|shared between calls|leak values", 2.5),
                    (r"encoding|file handle|use `?with`?|platform", 2.0), (r"\bbug\b|wrong|edge case", 1.0)],
    "design": [(r"type hints?|annotate", 2.5), (r"belongs in|design", 1.0)],
    "build_release": [(r"build (and|or) release|release scripts?|reproducib|fetch(es)? .* at build|reach the network|build time", 3.0)],
}
SOCIAL = re.compile(r"^(lgtm|looks good|thanks|thank you|nice|approved|fine by me|merging|great)[\s,.!:)]*", re.I)


def classify(text: str) -> tuple[str, float]:
    t = (text or "").lower()
    scores: Counter[str] = Counter()
    for cat, rules in LEXICON.items():
        for rx, w in rules:
            if re.search(rx, t):
                scores[cat] += w
    if scores.get("history_context", 0) >= 3.0:
        scores["history_context"] += 1.5
    if scores.get("tests") and (scores.get("docs") or scores.get("style")):
        scores["tests"] -= 1.0
    if not scores:
        return "question" if t.strip().endswith("?") else "correctness", 0.0
    cat, s = scores.most_common(1)[0]
    return cat, s


def severity_of(text: str, category: str) -> str:
    t = text.lower()
    if re.search(r"\bnit\b", t) or category == "style":
        return "nit"
    if re.search(r"never|must|has to|have to|breaks|can't review|needs (a|the)|always|escape|secret", t):
        return "major"
    if t.strip().endswith("?"):
        return "minor"
    return "minor"


# ------------------------------------------------------------------------------------------------ prompts
def extract_findings(inp: dict[str, Any]) -> dict[str, Any]:
    units = inp["_sim"]["units"]
    findings, non = [], []
    for u in units:
        body = (u.get("body") or "").strip()
        key = {"comment": "comment_ids", "review": "review_ids", "issue_comment": "issue_comment_ids",
               "rejection": "issue_comment_ids"}[u["kind"]]
        if u["kind"] == "review":
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
            concerns = []
            for p in paras:
                cat, score = classify(p)
                if score >= 1.5 and not SOCIAL.match(p) and not re.match(r"^(a few|some|close|thanks!? some|mostly|security review|a couple)", p, re.I):
                    concerns.append((p, cat))
            if not concerns:
                non.append({"source_ids": {key: [u["id"]]}, "reason": "social" if body else "empty"})
                continue
            for p, cat in concerns:
                findings.append(_finding({key: [u["id"]]}, p, cat, None))
            continue
        if u["kind"] == "comment" and u.get("reply"):
            cat, score = classify(body)
            if score < 2.5:
                non.append({"source_ids": {key: [u["id"]]}, "reason": "reply in a thread", "ack": True})
                continue
        cat, score = classify(body)
        if SOCIAL.match(body) and score < 2.0 or (u["kind"] == "issue_comment" and score < 1.5):
            clar = body.endswith("?")
            non.append({"source_ids": {key: [u["id"]]}, "reason": "clarifying question" if clar else "social"})
            continue
        anchor = {"scope": "line", "path": u.get("path"), "line": u.get("line")} if u.get("path") else None
        f = _finding({key: [u["id"]]}, body, cat, anchor)
        if u["kind"] == "rejection":
            f["kind"] = "rejection"
            f["severity"] = "blocker"
        findings.append(f)
    return {"findings": findings, "non_findings": non}


def _finding(ids: dict[str, list[int]], text: str, cat: str, anchor: dict[str, Any] | None) -> dict[str, Any]:
    q = text.strip().endswith("?")
    return {"source_ids": {"comment_ids": [], "review_ids": [], "issue_comment_ids": [], **ids},
            "anchor_hint": anchor, "category": cat, "severity": severity_of(text, cat),
            "kind": "question" if q and cat == "question" else ("change_request" if re.search(
                r"please|needs|has to|must|should", text, re.I) else "comment"),
            "statement": _first_sentence(text), "rationale": None, "suggestion": None,
            "is_question_challenge": bool(q and re.search(r"why|can this|what makes|really|safe", text, re.I))}


# The generic reviewer: (detector, category, severity, catch probability, wording)
GENERIC = [
    ("missing_tests", "tests", "minor", 0.9, "No tests cover the new function `{fn}`."),
    ("missing_docstring", "docs", "minor", 0.75, "Public function `{fn}` has no docstring."),
    ("mutable_default", "correctness", "major", 0.9, "Mutable default argument `{arg}` is shared between calls."),
    ("bare_except", "correctness", "major", 0.9, "Bare `except:` hides unrelated errors."),
    ("open_no_encoding", "correctness", "minor", 0.7, "`open()` without an explicit encoding uses the platform default; "
                                                      "pass `encoding=\"utf-8\"`."),
    ("unclosed_handle", "correctness", "minor", 0.8, "The file handle is not closed if an exception is raised before "
                                                     "`close()`; use a `with` block."),
    ("camel_case", "style", "nit", 0.6, "Variable `{name}` should be snake_case (PEP 8)."),
    ("regex_in_loop", "performance", "minor", 0.3, "Calling `re.match` for every character is slow; use string "
                                                    "methods or a precompiled pattern."),
    ("path_join_input", "security", "major", 0.25, "The path is built from an input name without validation; `..` "
                                                   "could reach files outside the base directory."),
    ("value_in_error", "security", "minor", 0.25, "The error message includes the variable's value, which may be "
                                                  "sensitive."),
    ("raise_builtin", "design", "nit", 0.08, "Consider a library-specific exception instead of `ValueError`."),
    ("sorts_output", "correctness", "minor", 0.1, "Sorting changes the output order compared with the input."),
    ("param_renamed", "api_compat", "major", 0.4, "Renaming the public parameter `{old}` breaks existing callers."),
    ("module_cache", "correctness", "minor", 0.15, "The module-level cache is never invalidated and is not "
                                                   "thread-safe."),
    ("runtime_dep", "dependency", "minor", 0.2, "This adds a new runtime dependency, `{dep}`."),
    ("unbounded_recursion", "security", "minor", 0.2, "The recursion has no depth limit."),
    ("network_in_script", "security", "major", 0.35, "The script downloads content at build time without an "
                                                     "integrity check."),
    ("binary_added", "tests", "nit", 0.3, "A binary test fixture was added; consider generating it in the test."),
    ("hallucinated_import", "correctness", "blocker", 0.85, "Imports `{mod}`, which doesn't exist in the package."),
    ("unused_helper", "design", "minor", 0.6, "`{fn}` is defined but never used."),
    ("always_fails", "tests", "major", 0.9, "The new test always fails (`assert False`)."),
    ("missing_hints", "design", "nit", 0.3, "Consider adding type hints to `{fn}`."),
    ("refactor_loop", "design", "nit", 0.35, "Consider extracting the loop body into a helper for readability."),
]


def _detect(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Generic static-review detectors over added lines. Returns hits (detector, path, line, values)."""
    hits: list[dict[str, Any]] = []
    files = {f["path"]: f for f in ctx["files"]}
    added: dict[str, list[list[Any]]] = ctx["added_lines"]
    removed: dict[str, list[list[Any]]] = ctx.get("removed_lines", {})
    test_changed = any(p.startswith("tests/") for p in files)
    defined = set()
    for lines in added.values():
        for _, t in lines:
            m = re.match(r"\s*def (\w+)\(", t)
            if m:
                defined.add(m.group(1))
    all_added_text = "\n".join(t for lines in added.values() for _, t in lines)
    for path, lines in added.items():
        f = files.get(path, {})
        if f.get("binary"):
            continue
        is_py = path.endswith(".py")
        is_test = path.startswith("tests/")
        in_loop_indent = None
        for i, (ln, t) in enumerate(lines):
            nxt = lines[i + 1][1] if i + 1 < len(lines) else ""
            if is_py and not is_test:
                m = re.match(r"(\s*)def ([a-z]\w*)\((.*)", t)
                if m and not m.group(2).startswith("_"):
                    fn = m.group(2)
                    if not test_changed:
                        hits.append({"d": "missing_tests", "path": path, "line": ln, "v": {"fn": fn}})
                    if '"""' not in nxt:
                        hits.append({"d": "missing_docstring", "path": path, "line": ln, "v": {"fn": fn}})
                    if "->" not in t and ":" in t and not re.search(r"\w+:\s*\w", m.group(3)):
                        hits.append({"d": "missing_hints", "path": path, "line": ln, "v": {"fn": fn}})
                mm = re.search(r"(\w+)(?::[^=,)]+)?\s*=\s*(\[\]|\{\})", t)
                if t.lstrip().startswith("def ") and mm:
                    hits.append({"d": "mutable_default", "path": path, "line": ln, "v": {"arg": mm.group(1) + "=[]"}})
                if re.match(r"\s*except\s*:", t):
                    hits.append({"d": "bare_except", "path": path, "line": ln, "v": {}})
                if re.search(r"\bopen\([^)]*\)", t) and "encoding" not in t and "'b'" not in t and '"rb"' not in t:
                    hits.append({"d": "open_no_encoding", "path": path, "line": ln, "v": {}})
                if re.match(r"\s*\w+ = open\(", t):
                    hits.append({"d": "unclosed_handle", "path": path, "line": ln, "v": {}})
                cm = re.match(r"\s*([a-z]+[A-Z][A-Za-z]+)(?::[^=]+)? = ", t)
                if cm:
                    hits.append({"d": "camel_case", "path": path, "line": ln, "v": {"name": cm.group(1)}})
                if re.match(r"\s*for .* in .*:", t):
                    in_loop_indent = len(t) - len(t.lstrip())
                    if _h(path, ln, "loop") < 0.5:
                        hits.append({"d": "refactor_loop", "path": path, "line": ln, "v": {}})
                elif in_loop_indent is not None and len(t) - len(t.lstrip()) <= in_loop_indent and t.strip():
                    in_loop_indent = None
                if in_loop_indent is not None and re.search(r"\bre\.(match|search|fullmatch)\(", t):
                    hits.append({"d": "regex_in_loop", "path": path, "line": ln, "v": {}})
                if re.search(r"os\.path\.join\(\w+, name\)", t) and "realpath" not in t:
                    hits.append({"d": "path_join_input", "path": path, "line": ln, "v": {}})
                if re.search(r"raise \w+\(f\"[^\"]*\{resolved", t):
                    hits.append({"d": "value_in_error", "path": path, "line": ln, "v": {}})
                if re.search(r"raise (ValueError|KeyError|RuntimeError)\(", t):
                    hits.append({"d": "raise_builtin", "path": path, "line": ln, "v": {}})
                if re.search(r"sorted\(|\.sort\(", t):
                    hits.append({"d": "sorts_output", "path": path, "line": ln, "v": {}})
                if re.search(r"^_CACHE\b|lru_cache", t):
                    hits.append({"d": "module_cache", "path": path, "line": ln, "v": {}})
                if re.search(r"def _walk_\w+\(.*depth", t) and "depth >" not in all_added_text:
                    hits.append({"d": "unbounded_recursion", "path": path, "line": ln, "v": {}})
                hm = re.match(r"\s*from ([\w.]+) import", t)
                if hm and ".compat" in hm.group(1):
                    hits.append({"d": "hallucinated_import", "path": path, "line": ln, "v": {"mod": hm.group(1)}})
                um = re.match(r"def (_\w+_helper2)\(", t)
                if um:
                    hits.append({"d": "unused_helper", "path": path, "line": ln, "v": {"fn": um.group(1)}})
            if is_test and re.search(r"assert False", t):
                hits.append({"d": "always_fails", "path": path, "line": ln, "v": {}})
            if path.startswith("scripts/") and re.search(r"urlopen|urllib\.request", t):
                hits.append({"d": "network_in_script", "path": path, "line": ln, "v": {}})
            if path == "pyproject.toml" and re.match(r'^dependencies = \[\s*"', t):
                dm = re.search(r'"([A-Za-z0-9_.\-]+)', t)
                hits.append({"d": "runtime_dep", "path": path, "line": ln, "v": {"dep": dm.group(1) if dm else "?"}})
    for path, lines in removed.items():
        for _ln, t in lines:
            m = re.match(r"\s*def ([a-z]\w*)\((.*)", t)
            if m and path.endswith(".py"):
                old = re.findall(r"(\w+)(?::[^=,]*)?\s*=", m.group(2))
                new_def = next((x for _, x in added.get(path, []) if re.match(rf"\s*def {m.group(1)}\(", x)), None)
                if new_def:
                    for o in old:
                        if not re.search(rf"\b{o}\b", new_def):
                            hits.append({"d": "param_renamed", "path": path,
                                         "line": next(n for n, x in added[path] if x == new_def), "v": {"old": o}})
    for f in ctx["files"]:
        if f.get("binary") and f.get("status") == "added":
            hits.append({"d": "binary_added", "path": f["path"], "line": None, "v": {}})
    return hits


def baseline_review(inp: dict[str, Any]) -> dict[str, Any]:
    ctx = inp["_sim"]["ctx"]
    spec = {d[0]: d for d in GENERIC}
    out = []
    seen = set()
    for hit in _detect(ctx):
        d, cat, sev, p, wording = spec[hit["d"]]
        if _h(ctx["number"], ctx["head_sha"][:8], hit["d"], hit["path"], hit["line"]) >= p:
            continue
        k = (hit["d"], hit["path"])
        if k in seen and hit["d"] in ("missing_tests", "missing_docstring", "camel_case", "open_no_encoding"):
            continue
        seen.add(k)
        stmt = wording.format(**{**{"fn": "this function", "arg": "skip=[]", "name": "x", "old": "the parameter",
                                    "dep": "a package", "mod": "this module"}, **hit["v"]})
        out.append({"path": hit["path"], "start_line": hit["line"], "end_line": hit["line"],
                    "scope": "line" if hit["line"] else "file", "category": cat, "severity": sev, "statement": stmt,
                    "rationale": None, "suggestion": None, "certainty": "high" if p >= 0.8 else "medium"})
    order = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}
    out.sort(key=lambda x: order[x["severity"]])
    return {"findings": out[: int(inp.get("max_findings", 15))]}


def match_findings(inp: dict[str, Any]) -> dict[str, Any]:
    out = []
    for p in inp["_sim"]["pairs"]:
        a, b = p["a"], p["b"]
        same_cat = a["category"] == b["category"]
        lex = max(float(p["lexical"]), similarity(a["statement"], b["statement"]))
        near = float(p["anchor"]) >= 0.6
        pr_level = p.get("reason") == "pr_level_same_category"
        if pr_level:
            if lex >= 0.12:
                dec, why = "match", "The same concern, raised for the whole PR on one side."
            else:
                dec, why = "partial", "Related concerns of the same kind."
        elif same_cat and (near or lex >= 0.3):
            dec, why = "match", "Same concern at the same place." if near else "Same concern, similar wording."
        elif near and lex >= 0.18:
            dec, why = "partial", "Same location; overlapping concerns that would be fixed together."
        elif same_cat and float(p["anchor"]) > 0 and lex >= 0.12:
            dec, why = "partial", "Same file and kind of concern; one is broader."
        else:
            dec, why = "none", "Different concerns."
        out.append({"pair_id": p["pair_id"], "decision": dec, "same_concern": dec == "match", "rationale": why})
    return {"decisions": out}


_STOP_TITLE = re.compile(r"^(please|could you|can we|i'd like|i think|so|also)\s+", re.I)


_DANGLING = {"a", "an", "the", "to", "of", "for", "in", "on", "with", "at", "and", "or", "is", "be", "that", "by",
             "its", "it's", "has", "have", "must", "should", "can"}


def _clean_title(s: str) -> str:
    s = re.sub(r"`[^`]*`", "", s)
    s = _STOP_TITLE.sub("", s).strip(" .,:;")
    s = re.sub(r"\b(to|of|for|in|on|with|at|from)\s*([,.;:])", r"\2", s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    words = s.split()[:8]
    while len(words) > 3 and words[-1].lower().strip(",.;:") in _DANGLING:
        words.pop()
    t = " ".join(words).strip(" ,.;:")
    return (t[0].upper() + t[1:]) if t else s


def lens_items(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    items = []
    for c in sim["clusters"]:
        ms = c["members"]
        stmts = [m["statement"] for m in ms]
        # the most central statement: highest mean similarity to the others
        best = max(range(len(stmts)), key=lambda i: sum(similarity(stmts[i], s) for s in stmts))
        central = stmts[best]
        short = min((s for s in stmts if len(s.split()) <= 14), key=lambda s: -sum(similarity(s, x) for x in stmts),
                    default=central)
        cat = Counter(m["category"] for m in ms).most_common(1)[0][0]
        paths = [m["path"] for m in ms if m["path"]]
        dirs = Counter(p.rsplit("/", 1)[0] for p in paths if "/" in p)
        top = dirs.most_common(2)
        if paths and sum(n for _, n in top) / len(paths) < 0.6:
            parts = [p.split("/") for p in paths if "/" in p]
            prefix = []
            for seg in zip(*parts, strict=False):
                if len(set(seg)) == 1:
                    prefix.append(seg[0])
                else:
                    break
            globs = [("/".join(prefix) + "/**") if prefix else "**/*.py"]
        else:
            globs = [f"{d}/*" for d, _ in top]
        if "pyproject.toml" in paths:
            globs.append("pyproject.toml")
        globs = globs or ["**/*.py"]
        bg = sim.get("background", {})
        toks = [set(m["code"]) | {t.rsplit(".", 1)[-1] for t in m["code"] if "." in t} for m in ms]
        code = Counter(t for ts in toks for t in ts)
        cands = []
        for t, n in code.items():
            rate = n / len(ms)
            lift = rate / max(bg.get(t, rate * 0.5), 1e-6)
            if rate >= 0.25 and lift >= 1.5 and len(t) > 3:
                cands.append((rate * lift, t))
        # greedy cover: distinctive tokens until most members are covered
        pats_t: list[str] = []
        covered: set[int] = set()
        for _, t in sorted(cands, reverse=True):
            gain = {i for i, ts in enumerate(toks) if t in ts} - covered
            if not gain:
                continue
            pats_t.append(t)
            covered |= gain
            if len(covered) / len(ms) >= 0.8 or len(pats_t) >= 3:
                break
        pats = [rf"\b{re.escape(t)}\b" for t in pats_t] if len(covered) / max(1, len(ms)) >= 0.6 else []
        refs = sorted({r for m in ms for r in m.get("refs", [])})
        rationale = " ".join(dict.fromkeys(re.split(r"(?<=[.!?])\s+", central)[1:2])) or \
            f"Raised on {len(ms)} past pull requests" + (f", including #{refs[0]}" if refs else "") + "."
        items.append({"cluster_ids": [c["cluster_id"]], "title": _clean_title(short), "statement": central,
                      "rationale": rationale, "category": cat, "triggers": {"paths": globs, "code_patterns": pats},
                      "exclude_sample_ids": [], "attach_sample_ids": []})
    return {"items": items}


def lens_card(inp: dict[str, Any]) -> dict[str, Any]:
    items = inp["_sim"]["items"]
    edge_v = [i for i in items if i["type"] == "edge" and i["status"] == "validated"]
    cand = [i for i in items if i["type"] == "edge" and i["status"] == "candidate"]
    bs = [i for i in items if i["type"] == "blind_spot"]
    sg = [i for i in items if i["type"] == "shared_ground"]
    bias = [i for i in items if i["status"] == "bias_suspected"]
    cats = Counter(i["category"] for i in edge_v)
    lead = ", ".join(c.replace("_", " ") for c, _ in cats.most_common(3)) or "a few areas"
    summary = (f"You notice things a generic reviewer misses, mostly about {lead}. "
               f"{len(edge_v)} patterns are proven by your reviews and {len(cand)} are still forming. "
               f"Generic review already covers {len(sg)} kinds of routine concern for you.")
    secs = [("What you notice", edge_v), ("Still learning", cand), ("Blind spots worth knowing", bs),
            ("Where generic review is enough", sg)]
    if inp.get("include_bias"):
        secs.append(("Possible bias", bias))
    return {"summary": summary, "sections": [{"heading": h, "bullets": [
        {"text": f"{i['title']}. (seen in {i['support']} reviews)", "item_ids": [i["id"]]} for i in rows]}
        for h, rows in secs if rows]}


def lens_recall(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    ctx = sim["ctx"]
    paths = [f["path"] for f in ctx["files"]]
    areas = {p.rsplit("/", 1)[0] for p in paths}
    items = [{"item_id": i, "why": "Its triggers match this change."} for i in sim["fired"]]
    for it in sim["items"]:
        if it["id"] in sim["fired"]:
            continue
        if any(g.rsplit("/", 1)[0] in areas for g in it["triggers"]["paths"]):
            items.append({"item_id": it["id"], "why": "Same area of the code."})
    q = set(tokens(ctx["title"])) | {t for p in paths for t in tokens(p)}
    scored = []
    for ln in sim["digest_lines"]:
        fid = ln[1:ln.index("]")]
        s = len(q & set(tokens(ln))) + (3 if any(p in ln for p in paths) else 0) + \
            (2 if any(a in ln for a in areas) else 0)
        if s > 1:
            scored.append((s, fid))
    scored.sort(key=lambda x: -x[0])
    return {"relevant_items": items[: int(inp.get("max_items", 8))],
            "relevant_findings": [{"finding_id": f, "why": "A past comment on the same code."}
                                  for _, f in scored[: int(inp.get("max_findings", 12))]]}


def lens_review(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    ctx = sim["ctx"]
    items = {i["id"]: i for i in sim["items"]}
    ex_by_item: dict[str, list[str]] = {}
    for e in sim["exemplars"]:
        ex_by_item.setdefault(e["item"], []).append(e["id"])
    out = []
    for iid, where in sim["fired"].items():
        it = items.get(iid)
        if it is None or it["type"] != "edge" or not where:
            continue
        if sim["counter"].get(iid):
            continue  # the change already does what this person asks for
        st = it.get("stats", {})
        has_patterns = bool(it["triggers"].get("code_patterns"))
        if not has_patterns and float(st.get("trigger_precision") or 0) < 0.5:
            continue
        path, line = where[0]
        cert = "high" if it["status"] == "validated" and int(st.get("support", 0)) >= 6 else (
            "medium" if it["status"] == "validated" else "low")
        out.append({"path": path, "start_line": line, "end_line": line, "scope": "line", "category": it["category"],
                    "severity": it.get("severity_typical", "minor"), "statement": it["statement"],
                    "rationale": it.get("rationale"), "suggestion": None, "certainty": cert, "title": it["title"],
                    "lens_item_ids": [iid], "exemplar_finding_ids": ex_by_item.get(iid, [])[:3],
                    "why_similar": f"Same kind of change as the cited past reviews ({it['title'].lower()})."})
    if sim.get("shared_categories"):
        spec = {d[0]: d for d in GENERIC}
        for hit in _detect(ctx):
            d = spec[hit["d"]]
            if d[1] in sim["shared_categories"] and hit["d"] in ("missing_tests", "missing_docstring", "camel_case",
                                                                 "mutable_default", "bare_except"):
                stmt = d[4].format(**{**{"fn": "this function", "name": "x"}, **hit["v"]})
                out.append({"path": hit["path"], "start_line": hit["line"], "end_line": hit["line"], "scope": "line",
                            "category": d[1], "severity": d[2], "statement": stmt, "rationale": None,
                            "suggestion": None, "certainty": "medium", "title": None, "lens_item_ids": ["routine"],
                            "exemplar_finding_ids": [], "why_similar": None})
    return {"findings": out[: int(inp.get("max_findings", 15))]}


GENERIC_BODY = re.compile(r"improves? the (overall )?code quality|best practices|enhance the user experience|"
                          r"significant improvement|more robust and maintainable|improved functionality", re.I)


def triage_signals(inp: dict[str, Any]) -> dict[str, Any]:
    ctx = inp["_sim"]["ctx"]
    title = ctx["title"].rstrip(".")
    verb = "Fixes" if re.match(r"(?i)fix|handle", title) else ("Reverts" if title.startswith("Revert") else "Changes")
    summary = f"{verb if verb != 'Changes' else ''}{' ' if verb != 'Changes' else ''}{title[0].lower() + title[1:] if verb != 'Changes' else title}."
    ev, score = [], 0.0
    if GENERIC_BODY.search(ctx["description"] or ""):
        score += 0.55
        ev.append("The description restates the change generically")
    added = "\n".join(t for lines in ctx["added_lines"].values() for _, t in lines)
    if re.search(r"from [\w.]+\.compat import", added):
        score += 0.25
        ev.append("Uses a helper from a module that doesn't exist")
    if re.search(r"def _\w+_helper2\(", added):
        score += 0.15
        ev.append("Adds an unused helper")
    if "assert False" in added:
        score += 0.15
        ev.append("Adds a test that always fails")
    words = set(re.findall(r"`([^`]+)`", ctx["description"] or ""))
    mentions = any(w in added for w in words) or any(f["path"] in (ctx["description"] or "") for f in ctx["files"])
    public = any(f["path"].endswith("__init__.py") for f in ctx["files"]) or bool(re.search(r"^def [a-z]", added, re.M))
    return {"summary": summary.strip(), "slop": {"score": round(min(score, 1.0), 2), "evidence": ev},
            "description_matches_diff": bool(mentions) or not words, "touches_public_api": public}


def review_draft(inp: dict[str, Any]) -> dict[str, Any]:
    fs = inp["_sim"]["findings"]
    order = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}
    fs = sorted(fs, key=lambda f: order.get(f["severity"], 2))
    blocking = [f for f in fs if f["severity"] in ("blocker", "major")]
    rest = [f for f in fs if f not in blocking]
    body = ["Thanks for this! A few things before it can go in." if blocking else "Thanks! A couple of small notes."]
    if blocking:
        body.append("\n**Needs a change**\n" + "\n".join(
            f"- {f['statement']}" + (f" (see {', '.join(f['citations'])})" if f["citations"] else "") for f in blocking))
    if rest:
        body.append("\n**Smaller things**\n" + "\n".join(f"- {f['statement']}" for f in rest))
    comments = [{"path": f["path"], "line": f["line"], "side": "RIGHT", "body_md": f["statement"] + (
        f"\n\nSuggested: {f['suggestion']}" if f.get("suggestion") else ""), "finding_id": f["id"]}
        for f in fs if f["path"] and f["line"]]
    return {"body_md": "\n".join(body), "comments": comments, "event": inp["_sim"]["event"]}


def slop_reply(inp: dict[str, Any]) -> dict[str, Any]:
    return {"body_md": inp["_sim"]["template"].strip()}


def handoff_note(inp: dict[str, Any]) -> dict[str, Any]:
    s = inp["_sim"]
    sig = [x for x in s["signals"] if not x.get("covered")] or s["signals"]
    names = ", ".join(x["label"].lower() for x in sig[:3])
    files = ", ".join(sorted({p for x in sig for p in x["paths"]})[:4])
    osv_line = ""
    for o in s.get("osv", []):
        osv_line += f" OSV: {o['name']} {o.get('version') or ''} — " + (", ".join(v["id"] for v in o["vulns"]) or
                                                                         "no known vulnerabilities") + "."
    note = (f"{s['target']}, could you look at #{s['pr_number']}? It touches {files} ({names}). Neither "
            f"{s['maintainer']}'s history nor the generic review covers this kind of change.{osv_line}")
    checks = {"build_script_changed": "Does the build or fixture script fetch anything from the network?",
              "ci_workflow_changed": "What does the new CI step run, and with which permissions?",
              "binary_added_or_changed": "Can the binary file be regenerated from a committed source?",
              "test_fixture_binary": "Is there a checksum for the fixture, and does it match the generator?",
              "new_dependency": "Is the new dependency needed at runtime, and who maintains it?",
              "exec_or_network_in_code": "Which URLs or commands are reached, and are they pinned?",
              "obfuscated_content": "What does the encoded content decode to?",
              "permissions_or_policy_changed": "Who gains or loses review rights?",
              "dependency_source_changed": "Is the package index or source still trusted and pinned?",
              "low_lens_coverage": "Is there someone who knows this area well?"}
    return {"note_md": note, "checklist": [checks[x["key"]] for x in sig if x["key"] in checks][:6]}


# --------------------------------------------------------------------------------------------------- fixes
def _file_of(findings: list[dict[str, Any]], files: dict[str, Any]) -> str | None:
    for f in findings:
        if f.get("path") in files and files[f["path"]]:
            return f["path"]
    return next((p for p, t in files.items() if t and not p.startswith("tests/")), None)


def _err_class(text: str) -> str:
    m = re.search(r"from [\w.]+\.errors import (\w+)", text)
    return m.group(1) if m else "ValueError"


def _module_of(path: str) -> str:
    return path[:-3].replace("/", ".")


def _containment_edits(path: str, text: str, strategy: str, args: bool) -> tuple[list[dict[str, str]], str]:
    cls = _err_class(text)
    tail = ", 0, 1" if args else ""
    edits = []
    m = re.search(r"^(\s+)(\w+) = os\.path\.join\(base_dir, name\)\n", text, re.M)
    if strategy == "realpath":
        if m:
            ind, var = m.group(1), m.group(2)
            edits.append({"path": path, "search": m.group(0), "replace":
                          f"{ind}root_real = os.path.realpath(root)\n{ind}{var} = os.path.realpath(os.path.join(base_dir, name))\n"
                          f"{ind}if os.path.commonpath([{var}, root_real]) != root_real:\n"
                          f"{ind}    raise {cls}(f\"include escapes the project root: {{name}}\"{tail})\n"})
        m2 = re.search(r"os\.path\.abspath\(root\)", text)
        if m2:
            edits.append({"path": path, "search": "os.path.abspath(root)", "replace": "os.path.realpath(root)"})
            m3 = re.search(r"os\.path\.abspath\(os\.path\.join\(base_dir, name\)\)", text)
            if m3:
                edits.append({"path": path, "search": m3.group(0), "replace": "os.path.realpath(os.path.join(base_dir, name))"})
        m4 = re.search(r"^(\s+)if os\.path\.isabs\(name\):\n\s+return name\n", text, re.M)
        if m4:
            edits.append({"path": path, "search": m4.group(0), "replace": ""})
        return edits, "Resolve the include with realpath and reject anything outside the real root (symlinks included)."
    # strategy "reject_names": refuse absolute names and '..' parts before joining
    if m:
        ind, var = m.group(1), m.group(2)
        edits.append({"path": path, "search": m.group(0), "replace":
                      f"{ind}if os.path.isabs(name) or \"..\" in name.replace(\"\\\\\", \"/\").split(\"/\"):\n"
                      f"{ind}    raise {cls}(f\"include escapes the project root: {{name}}\", 0, 1)\n{m.group(0)}"})
    return edits, "Reject absolute include names and any '..' segment before joining."


def _escape_test(path: str, text: str) -> dict[str, str] | None:
    m = re.search(r"^def (resolve_\w+_include)\(", text, re.M)
    if not m:
        return None
    fn, mod = m.group(1), _module_of(path)
    cls = _err_class(text)
    pkg = mod.split(".")[0]
    stem = path.rsplit("/", 1)[-1][:-3]
    return {"path": f"tests/test_include_{stem}_escape.py", "content":
            f"import os\n\nimport pytest\n\nfrom {pkg}.errors import {cls}\nfrom {mod} import {fn}\n\n\n"
            f"def test_{stem}_rejects_dotdot(tmp_path):\n    (tmp_path / \"outside.conf\").write_text(\"[a]\\n\", encoding=\"utf-8\")\n"
            f"    (tmp_path / \"proj\").mkdir()\n    with pytest.raises({cls}):\n"
            f"        {fn}(str(tmp_path / \"proj\"), \"../outside.conf\", str(tmp_path / \"proj\"))\n\n\n"
            f"def test_{stem}_rejects_symlink(tmp_path):\n    (tmp_path / \"secret\").mkdir()\n"
            f"    (tmp_path / \"secret\" / \"k.conf\").write_text(\"[a]\\n\", encoding=\"utf-8\")\n"
            f"    (tmp_path / \"proj\").mkdir()\n    os.symlink(tmp_path / \"secret\", tmp_path / \"proj\" / \"link\")\n"
            f"    with pytest.raises({cls}):\n        {fn}(str(tmp_path / \"proj\"), \"link/k.conf\", str(tmp_path / \"proj\"))\n"}


def _generic_edits(path: str, text: str, cat: str, statement: str) -> list[dict[str, str]]:
    edits: list[dict[str, str]] = []
    s = statement.lower()
    if "encoding" in s:
        for m in re.finditer(r"open\((\w+(?:\[\d\])?)\)", text):
            edits.append({"path": path, "search": m.group(0), "replace": f'open({m.group(1)}, encoding="utf-8")'})
    if "handle" in s or "with" in s and "close" in s:
        m = re.search(r"^(\s+)fh = open\((.+)\)\n((?:\1.*\n)*?)\1fh\.close\(\)\n", text, re.M)
        if m:
            ind, arg, body = m.group(1), m.group(2), m.group(3)
            new_body = "".join(ind + "    " + ln[len(ind):] + "\n" for ln in body.rstrip("\n").split("\n"))
            edits.append({"path": path, "search": m.group(0), "replace": f"{ind}with open({arg}) as fh:\n{new_body}"})
    if "mutable default" in s or "=[]" in s or "shared between calls" in s:
        m = re.search(r"skip: list\[str\] = \[\]", text)
        if m:
            edits.append({"path": path, "search": m.group(0), "replace": "skip: list[str] | None = None"})
        m2 = re.search(r"^(\s+)skip\.append\(", text, re.M)
        if m2:
            edits.append({"path": path, "search": m2.group(0), "replace": f"{m2.group(1)}skip = list(skip or [])\n{m2.group(0)}"})
    if "docstring" in s:
        m = re.search(r"^(def ([a-z]\w*)\(.*\).*:)\n", text, re.M)
        if m:
            edits.append({"path": path, "search": m.group(0), "replace": f'{m.group(1)}\n    """{m.group(2).replace("_", " ").capitalize()}."""\n'})
    if "value" in s and ("error" in s or "secret" in s or "message" in s):
        m = re.search(r'f"invalid value \{resolved!r\} for \{name\}"', text)
        if m:
            edits.append({"path": path, "search": m.group(0), "replace": 'f"invalid value for {name}"'})
    if "regex" in s or "per character" in s or "per-character" in s or cat == "performance":
        m = re.search(r're\.match\(r"\[\\s(.)\]", ch\)', text)
        if m:
            edits.append({"path": path, "search": m.group(0), "replace": f"ch.isspace() or ch == {m.group(1)!r}"})
            if text.count("re.") == 1:
                edits.append({"path": path, "search": "import re\n", "replace": ""})
    if "laminaerror" in s or "line and" in s or "hierarchy" in s:
        cls = _err_class(text)
        for m in re.finditer(r'raise ValueError\((f?"[^"]*")\)', text):
            edits.append({"path": path, "search": m.group(0), "replace": f"raise {cls}({m.group(1)}, 0, 1)"})
    if "sort" in s or "order" in s or "round" in s:
        m = re.search(r"for item in sorted\(section\.items, key=lambda i: getattr\(i, \"key\", \"\"\)\):", text)
        if m:
            edits.append({"path": path, "search": m.group(0), "replace": "for item in section.items:"})
        m2 = re.search(r"^\s+target\.items\.sort\(.*\)\n", text, re.M)
        if m2:
            edits.append({"path": path, "search": m2.group(0), "replace": ""})
    if "cache" in s or cat == "history_context":
        for pat in (r"^_CACHE: dict\[str, Document\] = \{\}\n\n?", r"^\s+if path in _CACHE:\n\s+return _CACHE\[path\]\n",
                    r"^\s+_CACHE\[path\] = doc\n"):
            m = re.search(pat, text, re.M)
            if m:
                edits.append({"path": path, "search": m.group(0), "replace": ""})
    return edits


def _smoke_test(path: str, text: str) -> dict[str, str] | None:
    m = re.search(r"^def ([a-z]\w*)\(", text, re.M)
    if not m:
        return None
    stem = path.rsplit("/", 1)[-1][:-3]
    area = path.split("/")[-2] if "/" in path else "pkg"
    return {"path": f"tests/test_{area}_{stem}_keeper.py",
            "content": f"from {_module_of(path)} import {m.group(1)}\n\n\ndef test_{stem}_is_importable():\n"
                       f"    assert callable({m.group(1)})\n"}


def fix_plan(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    files = sim["originals"]
    fs = sim["findings"]
    branch = sim["branch"]
    path = _file_of(fs, files)
    if path is None:
        return {"plan": "No file to change.", "edits": [], "new_files": [], "tests_to_run": [], "risk_notes": None}
    text = files[path] or ""
    edits: list[dict[str, str]] = []
    new_files: list[dict[str, str]] = []
    plan = []
    for f in fs:
        s = f["statement"].lower()
        if f["category"] == "security" and re.search(r"root|escape|symlink|confine|travers|\.\.", s):
            strategy = "realpath" if branch == "A" else "reject_names"
            e, p = _containment_edits(path, text, strategy, args=(branch != "A"))
            edits += e
            plan.append(p)
            t = _escape_test(path, text)
            if t:
                new_files.append(t)
        elif f["category"] == "tests" or "test" in s:
            t = _smoke_test(path, text)
            if t and t["path"] not in files:
                new_files.append(t)
                plan.append("Add a test that imports and calls the new function.")
        else:
            e = _generic_edits(path, text, f["category"], f["statement"])
            edits += e
            if e:
                plan.append(f"Address: {f['statement']}")
    seen, uniq = set(), []
    for e in edits:
        k = (e["path"], e["search"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    tests = [n["path"] for n in new_files] + [t for t in inp.get("tests_layout", []) if t in files][:3]
    return {"plan": " ".join(plan) or "No safe automatic change found for this finding.", "edits": uniq,
            "new_files": new_files, "tests_to_run": tests, "risk_notes": None}


def fix_repair(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    failure = sim["failure"]
    files = sim["files"]
    fs = sim["findings"]
    path = _file_of(fs, files)
    text = files.get(path) or "" if path else ""
    edits: list[dict[str, str]] = []
    new_files: list[dict[str, str]] = []
    note = ""
    m = re.search(r"missing (\d) required positional arguments?: '(\w+)'(?: and '(\w+)')?", failure)
    if m and path:
        cls = _err_class(text)
        for mm in re.finditer(rf"raise {cls}\((f\"[^\"]*\")\)", text):
            edits.append({"path": path, "search": mm.group(0), "replace": f"raise {cls}({mm.group(1)}, 0, 1)"})
        note = f"{cls} takes a line and a column; pass them."
    elif "does not address the finding" in failure and path:
        e, p = _containment_edits(path, text, "realpath", args=True)
        edits = e
        note = "The name check misses symlinks: " + p
    elif "search text not found" in failure and path:
        plan = fix_plan({"_sim": {"originals": files, "findings": fs, "branch": sim["branch"]},
                         "tests_layout": []})
        edits, new_files = plan["edits"], []
        note = "Re-planned against the current file."
    elif "F401" in failure and path:
        for mm in re.finditer(r"^import (re|sys|os)\n", text, re.M):
            mod = mm.group(1)
            if text.count(f"{mod}.") == 0:
                edits.append({"path": path, "search": mm.group(0), "replace": ""})
        note = "Remove the import that's no longer used."
    else:
        note = "No further change found."
    return {"plan": note, "edits": edits, "new_files": new_files,
            "tests_to_run": [p for p in files if p.startswith("tests/") and "escape" in p][:2], "risk_notes": None}


def fix_verify(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    diff_files = sim["files"]
    original = sim["originals"]
    added = "\n".join(t for t in diff_files.values() if t)
    for f in sim["findings"]:
        s = f["statement"].lower()
        if f["category"] == "security" and re.search(r"symlink|realpath|root|escape", s) and \
                not ("realpath" in added and ("commonpath" in added or "is_relative_to" in added)):
            return {"addresses_finding": False, "explanation": "Names are checked, but a symlink inside the project "
                                                              "can still point outside the root."}
        if "encoding" in s and 'encoding="utf-8"' not in added:
            return {"addresses_finding": False, "explanation": "open() still has no explicit encoding."}
        if "test" in s and not any(p.startswith("tests/") and p not in original for p in diff_files):
            return {"addresses_finding": False, "explanation": "No test was added."}
    return {"addresses_finding": bool(diff_files), "explanation": "The change addresses the finding and the tests pass."}


def calibration_notes(inp: dict[str, Any]) -> dict[str, Any]:
    n = inp["numbers"]
    prs = inp["_sim"].get("bad_prs", [])
    k, m = int(n["k_bad"] or 0), int(n["n_ignored"] or 0)
    tail = f" ({', '.join(f'#{x}' for x in prs[:3])})" if prs else ""
    return {"explanation": f"This was raised {n['support']} times. When it was not acted on, {k} of {m} times a "
                           f"problem followed{tail}."}


def lens_diff_summary(inp: dict[str, Any]) -> dict[str, Any]:
    ch = inp["changes"]
    by = Counter(c["change"] for c in ch)
    added = [c["title"] for c in ch if c["change"] == "added"]
    out = []
    if added:
        out.append(f"Started noticing: {added[0]}" + (f" and {len(added) - 1} more" if len(added) > 1 else "") + ".")
    if by.get("retired"):
        out.append(f"Stopped flagging {by['retired']} pattern(s).")
    if by.get("strengthened") or by.get("weakened"):
        out.append(f"{by.get('strengthened', 0)} pattern(s) more sure, {by.get('weakened', 0)} less sure.")
    if by.get("status_changed"):
        out.append(f"{by['status_changed']} status change(s).")
    return {"bullets": (out or ["No changes."])[:3]}


HINTS = {"security": "input that comes from a configuration file", "invariant": "what has to stay the same when the "
         "file is read and written back", "performance": "the work done for every character",
         "history_context": "what happened the last time this area changed", "api_compat": "what existing callers pass",
         "tests": "which paths through the code no test exercises", "docs": "what a user of this function would need to know",
         "correctness": "error paths and platform differences", "design": "the public signature",
         "dependency": "what gets installed for every user", "build_release": "what runs at build time"}


def practice_coach(inp: dict[str, Any]) -> dict[str, Any]:
    f = inp["_sim"]["finding"]
    where = f["anchor"].get("path") or "the change"
    line = f["anchor"].get("start_line")
    return {"hint": f"Look again at {where}" + (f" around line {line}" if line else "") +
                    f": think about {HINTS.get(f['category'], 'what could go wrong for a user')}."}


def practice_score(inp: dict[str, Any]) -> dict[str, Any]:
    sim = inp["_sim"]
    dec = []
    matched_notes = set()
    for p in sim["pairs"]:
        a, b = p["a"], p["b"]
        lex = similarity(a["statement"], b["statement"])
        near = float(p["anchor"]) >= 0.6
        cat_a, _ = classify(a["statement"])
        same = cat_a == b["category"]
        if (near and (same or lex >= 0.12)) or lex >= 0.3 or (same and float(p["anchor"]) > 0 and lex >= 0.08):
            d = "match"
        elif near:
            d = "partial"
        else:
            d = "none"
        if d != "none":
            matched_notes.add(a["refs"]["note_id"])
        dec.append({"pair_id": p["pair_id"], "decision": d, "rationale": "Same concern." if d == "match" else ""})
    fb = []
    base = sim.get("baseline", [])
    for n in sim["notes"]:
        if n["id"] in matched_notes:
            fb.append({"note_id": n["id"], "verdict": "matches", "line": None})
            continue
        text = n["text"].lower()
        valid = any(b["anchor"].get("path") == n.get("path") and b["category"] == "correctness" for b in base) and \
            re.search(r"encoding|leave[s]? it open|close|handle|raises", text)
        if valid:
            fb.append({"note_id": n["id"], "verdict": "valid_other", "line": None})
        elif re.search(r"rename|shorter|comprehension|formatting|is this function needed", text):
            fb.append({"note_id": n["id"], "verdict": "not_an_issue", "line": None})
        else:
            fb.append({"note_id": n["id"], "verdict": "unclear", "line": None})
    return {"decisions": dec, "feedback": fb}


def assistant_title(inp: dict[str, Any]) -> dict[str, Any]:
    words = re.sub(r"[^\w#' -]", "", inp.get("text", "")).split()
    return {"title": " ".join(words[:6]) or "New chat"}


PROMPTS = {"extract_findings": extract_findings, "baseline_review": baseline_review, "match_findings": match_findings,
           "lens_items": lens_items, "lens_card": lens_card, "lens_recall": lens_recall, "lens_review": lens_review,
           "triage_signals": triage_signals, "review_draft": review_draft, "slop_reply": slop_reply,
           "handoff_note": handoff_note, "fix_plan": fix_plan, "fix_repair": fix_repair, "fix_verify": fix_verify,
           "calibration_notes": calibration_notes, "lens_diff_summary": lens_diff_summary,
           "practice_coach": practice_coach, "practice_score": practice_score, "assistant_title": assistant_title}


def run(prompt_id: str, inputs: dict[str, Any], **_: Any) -> Any:
    fn = PROMPTS.get(prompt_id)
    if fn is not None and "_sim" in inputs or prompt_id in ("assistant_title", "lens_diff_summary", "calibration_notes"):
        try:
            return fn(inputs)  # type: ignore[misc]
        except KeyError:
            pass
    from keeper.llm.prompts import load_prompt
    from keeper.llm.schemas import load_schema, minimal_instance
    p = load_prompt(prompt_id)
    return minimal_instance(load_schema(p.output_schema)) if p.output_schema else ""


# ---------------------------------------------------------------------------------------------- assistant
def assistant(messages: list[dict[str, Any]], tools: list[dict[str, Any]], inputs: dict[str, Any]) -> Any:
    from keeper.llm.providers import ProviderResponse
    from keeper.llm.simulate.chat import respond
    return respond(messages, tools, inputs, ProviderResponse)


_ = json

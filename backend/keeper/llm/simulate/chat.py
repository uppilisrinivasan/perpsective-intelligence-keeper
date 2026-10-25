"""Offline assistant (LLM_PROVIDER=fake): picks tools by intent, then writes an answer from the tool results only,
citing them with [[type:id]] markers. Deterministic; every answer is labelled as an offline simulation upstream."""

from __future__ import annotations

import json
import re
from typing import Any

LANES = {"edge": "Needs your eye", "blind_spot": "Worth a second look", "unknown": "Needs another reviewer",
         "shared": "Handled for you", "baseline_only": "Other model notes"}
_STOP = {"the", "a", "an", "me", "my", "like", "show", "past", "comments", "comment", "about", "what", "for", "of",
         "to", "in", "on", "is", "are", "and", "or", "with", "this", "that", "please", "find", "search"}


def _call(i: int, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"id": f"call_{i}_{name}", "name": name, "arguments": json.dumps(args)}


def _number(q: str, ctx: dict[str, Any]) -> int | None:
    m = re.search(r"#(\d+)|\bpr\s*(\d+)\b", q)
    if m:
        return int(m.group(1) or m.group(2))
    n = ctx.get("number")
    return int(n) if n else None


def plan(q: str, ctx: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    ql = q.lower()
    n = _number(ql, ctx)
    screen = ctx.get("screen")
    quoted = re.findall(r"[“\"]([^”\"]+)[”\"]", q)
    if re.search(r"\b(what is|what's a|what does .* mean|explain the term|define)\b", ql) and not n and \
            "lens miss" not in ql and "result" not in ql:
        term = quoted[0] if quoted else re.sub(r".*(what is|what's a|define|explain the term)\s+", "", ql).strip(" ?.")
        return [("explain_concept", {"term": term})]
    if quoted or re.search(r"\b(past comments|search|said about|history of)\b", ql):
        query = quoted[0] if quoted else " ".join(w for w in re.findall(r"[a-z_]+", ql) if w not in _STOP)
        return [("search_history", {"query": query or ql})]
    if n and re.search(r"\bfix\b", ql):
        return [("get_pull", {"number": n}), ("propose_fix", {"number": n})]
    if n and re.search(r"hand.?off|another reviewer|who should", ql):
        return [("get_pull", {"number": n}), ("propose_handoff", {"number": n})]
    if n and re.search(r"\b(analy[sz]e|re-?run|again)\b", ql):
        return [("propose_analyze", {"number": n})]
    if re.search(r"\b(changed|since v|diff|new in)\b", ql) and "lens" in ql:
        return [("diff_lens_versions", {})]
    if re.search(r"\b(proof|proven|fidelity|result|pass)\b", ql) or screen == "proof" and not n:
        if re.search(r"\b(run|start)\b", ql) and "result" not in ql:
            return [("propose_fidelity_run", {})]
        return [("get_proof", {})]
    if re.search(r"practi[cs]e|growth|getting better|health", ql) or screen == "practice":
        return [("get_growth", {}), ("propose_practice", {})] if re.search(r"practi[cs]e", ql) else [("get_growth", {})]
    if re.search(r"\b(spend|spent|cost|usage|budget used)\b", ql):
        return [("get_usage", {})]
    if re.search(r"rebuild", ql):
        return [("propose_rebuild_lens", {"reason": q[:120]})]
    if "lens" in ql or re.search(r"\b(miss|blind spot)", ql) or screen == "lens":
        return [("get_lens", {})]
    if n:
        return [("get_pull", {"number": n})]
    if re.search(r"handled|shared", ql):
        return [("get_queue", {"lane": "shared"})]
    if re.search(r"another reviewer|unknown", ql):
        return [("get_queue", {"lane": "unknown"})]
    return [("get_queue", {})]


def _pct(x: Any) -> str:
    return "—" if x is None else f"{float(x) * 100:.0f}%"


def _queue(r: dict[str, Any], who: str) -> str:
    s = r.get("summary", {})
    rows = r.get("rows", [])
    lines = []
    if s:
        lines.append(f"**{s.get('need_count', 0)} of {s.get('total', 0)}** open pull requests need {who}'s eye, about "
                     f"{s.get('attention_minutes_total', 0)} of {s.get('budget_minutes', 0)} minutes this week.")
    for row in rows[:6]:
        why = row["reasons"][0] if row.get("reasons") else ""
        lines.append(f"- [[pull:{row['number']}]] {row['title']} · {LANES.get(row['lane'], row['lane'])}"
                     + (f" ({why})" if why else ""))
    if not rows:
        lines.append("Nothing is in that lane right now.")
    return "\n".join(lines)


def _pull(r: dict[str, Any], who: str) -> str:
    if r.get("error"):
        return f"I couldn't read that pull request: {r['error']}"
    lane = r.get("lane")
    head = f"[[pull:{r['number']}]] **{r['title']}**"
    if not lane:
        return head + " hasn't been sorted yet."
    lines = [f"{head} is in **{LANES.get(lane, lane)}**."]
    if r.get("summary"):
        lines.append(r["summary"])
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for f in r.get("findings", []):
        by_lane.setdefault(f["lane"], []).append(f)
    for ln in ("edge", "blind_spot", "unknown", "shared"):
        fs = by_lane.get(ln, [])
        if not fs:
            continue
        intro = {"edge": f"What {who} would notice that generic review doesn't:", "blind_spot":
                 "Worth a second look (generic review catches it; it has mattered before):",
                 "unknown": "Outside what the lens knows:", "shared": "Handled for you:"}[ln]
        lines.append(intro)
        for f in fs[:4]:
            where = f" in `{f['path']}`" if f.get("path") else ""
            lines.append(f"- [[finding:{f['id']}]] {f['title']}{where}")
    sig = [s["label"] for s in r.get("signals", []) if not s.get("covered")]
    if sig:
        lines.append("Risk signals no one in the lens covers: " + ", ".join(sig) + ".")
    return "\n".join(lines)


def _lens(r: dict[str, Any], q: str) -> str:
    items = r.get("items", [])
    if "miss" in q.lower() or "blind" in q.lower():
        bs = [i for i in items if i["type"] == "blind_spot"]
        if not bs:
            return ("The lens has no validated blind spots yet: generic review hasn't caught anything this maintainer "
                    "tends to miss often enough, with bad outcomes, to count.")
        return "Things generic review catches that tend to be missed, with bad outcomes before:\n" + "\n".join(
            f"- [[lens_item:{i['id']}]] {i['title']} (seen {i['support']} times)" for i in bs[:6])
    lines = [f"Lens v{r.get('version')} for {r.get('person')} ({r.get('status')})."]
    edge = [i for i in items if i["type"] == "edge" and i["status"] == "validated"]
    if edge:
        lines.append("What it notices that generic review misses:")
        lines += [f"- [[lens_item:{i['id']}]] {i['title']} (support {i['support']})" for i in edge[:6]]
    if r.get("shared_ground"):
        lines.append("Generic review already covers: " + ", ".join(r["shared_ground"][:5]) + ".")
    return "\n".join(lines)


def _diff(r: dict[str, Any]) -> str:
    if r.get("error"):
        return f"I couldn't compare versions: {r['error']}"
    lines = [r.get("summary", "").split("\n")[0]]
    for k, label in (("added", "New"), ("changed", "Changed"), ("removed", "Retired")):
        for e in r.get(k, [])[:4]:
            lines.append(f"- {label}: [[lens_item:{e['id']}]] {e['title']}" + (f" ({e['detail']})" if e.get("detail")
                                                                              else ""))
    return "\n".join(lines)


def _proof(r: dict[str, Any]) -> str:
    if not r.get("run_id"):
        return "There's no Fidelity Test result yet."
    d = r.get("difference", {})
    verdict = "passed" if r.get("pass") else "did not pass"
    sim = " This run used the offline simulator, not Nemotron, so treat the numbers as a demonstration." \
        if r.get("simulated") else ""
    lines = [f"On {r.get('prs')} held-out pull requests the lens never saw, Keeper recovered {_pct(r.get('keeper_recall'))} "
             f"of what the maintainer raised, against {_pct(r.get('generic_recall'))} for generic review: a difference "
             f"of {_pct(d.get('value'))} (90% interval {_pct(d.get('low'))} to {_pct(d.get('high'))}) "
             f"[[metric:recall_difference]]. The test **{verdict}** [[metric:overall]].{sim}"]
    failed = [c["label"] for c in r.get("criteria", []) if c.get("passed") is False]
    if failed:
        lines.append("Criteria not met: " + "; ".join(failed) + ".")
    return "\n".join(lines)


def _growth(r: dict[str, Any]) -> str:
    if r.get("error"):
        return f"I couldn't read growth: {r['error']}"
    lines = [f"Lens health: **{r.get('health', 'insufficient_data').replace('_', ' ')}**. {r.get('explanation', '')}"]
    if r.get("new_things_noticed"):
        lines.append("Recently noticed for the first time: " + "; ".join(r["new_things_noticed"][:3]) + ".")
    return "\n".join(lines)


def _search(r: dict[str, Any]) -> str:
    res = r.get("results", [])
    if not res:
        return "I couldn't find past review comments about that."
    return "Past review comments:\n" + "\n".join(f"- [[comment:{c['id']}]] {c.get('author')} on #{c['pr']}: "
                                                   f"“{c['excerpt'][:140]}”" for c in res[:5])


def _usage(r: dict[str, Any]) -> str:
    return f"This {r.get('period')}: {r.get('calls', 0)} model calls, ${float(r.get('total_usd') or 0):.2f} in total."


def _concept(r: dict[str, Any]) -> str:
    if not r.get("found"):
        return "I don't have that term. Known terms: " + ", ".join(r.get("known_terms", [])[:12]) + "."
    return f"**{r['label']}**: {r['short']}" + (f"\n\n{r['long']}" if r.get("long") else "")


def compose(q: str, results: list[dict[str, Any]], who: str) -> str:
    parts = []
    proposed = False
    for x in results:
        r, name = x["result"], x["name"]
        if x.get("status") == "error" and not name.startswith("propose_"):
            parts.append(f"I couldn't get that: {r.get('error')}.")
            continue
        if name.startswith("propose_"):
            proposed = True
            if r.get("suggested"):
                parts.append(f"Suggested reviewer: **{r['suggested']['login']}**"
                             + (f" ({'; '.join(r['suggested']['why'])})" if r['suggested'].get("why") else "") + ".")
            continue
        writers = {"get_queue": lambda r: _queue(r, who), "get_pull": lambda r: _pull(r, who),
                   "get_lens": lambda r: _lens(r, q), "diff_lens_versions": _diff, "get_proof": _proof,
                   "get_growth": _growth, "search_history": _search, "get_usage": _usage,
                   "explain_concept": _concept}
        parts.append(writers.get(name, lambda r: "")(r))
    if proposed:
        parts.append("I've prepared it below; nothing runs until you confirm.")
    return "\n\n".join(p for p in parts if p) or "I don't know; the tools didn't return anything for that."


def respond(messages: list[dict[str, Any]], tools: list[dict[str, Any]], inputs: dict[str, Any], response_cls: Any
            ) -> Any:
    sim = inputs.get("_sim") or {}
    q = sim.get("question") or next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    ctx = sim.get("context") or {}
    results = sim.get("results") or []
    names = {t["function"]["name"] for t in tools}
    if not results and tools:
        steps = [(n, a) for n, a in plan(q, ctx) if n in names]
        first = [s for s in steps if s[0] != "propose_fix"]
        if first:
            return response_cls(text="", tool_calls=[_call(i, n, a) for i, (n, a) in enumerate(first)],
                                finish_reason="tool_calls")
    done = {x["name"] for x in results}
    if tools and "propose_fix" in [n for n, _ in plan(q, ctx)] and "propose_fix" not in done:
        pull = next((x["result"] for x in results if x["name"] == "get_pull"), {})
        ids = [f["id"] for f in pull.get("findings", []) if f.get("fixable") and f["lane"] in ("shared", "edge")][:3]
        if ids:
            return response_cls(text="", tool_calls=[_call(len(results), "propose_fix",
                                                           {"number": pull["number"], "finding_ids": ids})],
                                finish_reason="tool_calls")
        results = [*results, {"name": "note", "result": {}, "status": "done"}]
    return response_cls(text=compose(q, [x for x in results if x["name"] != "note"], sim.get("maintainer") or "the maintainer"),
                        finish_reason="stop")

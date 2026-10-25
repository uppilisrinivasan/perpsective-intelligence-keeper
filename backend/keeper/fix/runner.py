"""The fix loop (methodology 08): plan → apply → test → (repair)* → verify, in a sandbox, with two branches from
one checkpoint. The model proposes edits and test paths only; every command comes from the recipe."""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from keeper.analysis import codeindex
from keeper.config import get_config
from keeper.core.errors import KeeperError, SandboxUnavailable
from keeper.db import models as M
from keeper.fix import edits as E
from keeper.ids import new_id
from keeper.sandbox import recipes as RC
from keeper.sandbox.base import FileChange
from keeper.sandbox.select import select as select_sandbox
from keeper.sources import git as G
from keeper.sources import junit


def _tests_for(paths: list[str], all_files: list[str]) -> list[str]:
    tests = [p for p in all_files if p.startswith("tests/") and p.endswith(".py")]
    out = []
    for p in paths:
        stem = p.rsplit("/", 1)[-1].removesuffix(".py")
        parent = p.rsplit("/", 2)[-2] if p.count("/") >= 1 else ""
        out += [t for t in tests if stem in t or (parent and f"test_{parent}" in t)]
    return sorted(set(out))[:12]


def _excerpt(text: str, lines: list[int], cfg: dict[str, Any]) -> str:
    rows = text.split("\n")
    if len(rows) <= int(cfg["whole_file_max_lines"]) or not lines:
        return text
    keep: set[int] = set()
    for ln in lines:
        keep.update(range(max(1, ln - int(cfg["context_lines"])), min(len(rows), ln + int(cfg["context_lines"])) + 1))
    out, last = [], 0
    for i in sorted(keep):
        if i != last + 1:
            out.append("# … lines omitted …")
        out.append(rows[i - 1])
        last = i
    return "\n".join(out)


class FixRunner:
    def __init__(self, gateway: Any, job: Any = None):
        self.gw = gateway
        self.job = job
        self.cfg = get_config()

    async def emit(self, kind: str, data: dict[str, Any]) -> None:
        if self.job is not None:
            await self.job.event(kind, data)

    async def run(self, db: Session, project: M.Project, pr: M.Pull, analysis: M.Analysis | None,
                  findings: list[dict[str, Any]], *, branches: int | None = None, user_hint: str | None = None,
                  both_ways: bool = False, origin: str = "live", fix_id: str | None = None,
                  diff_text: str = "") -> M.FixRun:
        fcfg = self.cfg.fix
        nb = int(branches or fcfg["branches"])
        run = M.FixRun(id=fix_id or new_id("fix"), project_id=project.id, pr_number=pr.number,
                       analysis_id=analysis.id if analysis else None, finding_ids=[f["id"] for f in findings],
                       status="preparing", job_id=self.job.id if self.job else None, origin=origin)
        db.add(run)
        db.flush()
        await self.emit("fix.started", {"finding_ids": run.finding_ids, "branches": nb})
        t_start = time.time()
        runner, reason, _ = await select_sandbox()
        run.provider, run.provider_reason = runner.name, reason
        files_at_head = G.ls_tree(project.repo_path, analysis.head_sha if analysis else pr.head_sha)
        recipe_name = RC.detect(files_at_head)
        if recipe_name is None:
            run.status, run.error = "failed", "Fixes not available for this language yet"
            db.flush()
            await self.emit("fix.completed", {"status": "failed", "winning_branch": None, "diff_stats": {}})
            return run
        recipe = RC.recipes()[recipe_name]
        head = analysis.head_sha if analysis else pr.head_sha
        try:
            ws0 = await runner.prepare(project.repo_path, head, recipe, recipe_name)
        except SandboxUnavailable as e:
            run.status, run.error = "failed", e.message
            db.flush()
            await self.emit("fix.completed", {"status": "failed", "winning_branch": None, "diff_stats": {},
                                              "error": e.message})
            return run
        await self.emit("fix.sandbox.ready", {"provider": runner.name})
        base = await self.test(runner, ws0, recipe, None)
        run.baseline_failures = [f["test"] for f in base["failures"]]
        run.junit_summary = {"baseline": {k: base[k] for k in ("passed", "failed", "skipped", "time")}}
        await self.emit("fix.tests.baseline", {"passed": base["passed"], "failed": base["failed"]})
        cp0 = await runner.checkpoint(ws0)
        anchors: dict[str, list[int]] = {}
        for f in findings:
            if f["anchor"].get("path"):
                anchors.setdefault(f["anchor"]["path"], []).append(f["anchor"].get("start_line") or 1)
        originals: dict[str, str | None] = {}
        for p in set(anchors) | set(_tests_for(list(anchors), files_at_head)):
            originals[p] = await runner.read_file(ws0, p)
        idx = codeindex.build(project.repo_path, head)
        pyproject = originals.get("pyproject.toml") or G.show(project.repo_path, head, "pyproject.toml") or ""
        ll = re.search(r"line-length\s*=\s*(\d+)", pyproject)
        base_inputs = {
            "findings": [{"id": f["id"], "category": f["category"], "path": f["anchor"].get("path") or "",
                          "line": f["anchor"].get("start_line") or 0, "statement": f.get("user_text") or f["statement"],
                          "suggestion": f.get("suggestion")} for f in findings],
            "files": [{"path": p, "content": _excerpt(t or "", anchors.get(p, []), fcfg["file_excerpt"])}
                      for p, t in sorted(originals.items()) if t is not None],
            "diff": diff_text,
            "repo_map": codeindex.summary(idx, 3000), "tests_layout": _tests_for(list(anchors), files_at_head),
            "style": f"line length {ll.group(1) if ll else 'default'}; ruff; type hints on public functions",
            "user_hint": user_hint, "other_plan": None}
        names = ["A", "B"][:max(1, nb)]
        temps = fcfg.get("branch_temperatures", {"A": 0.2, "B": 0.7})
        state: dict[str, dict[str, Any]] = {}
        winner: list[str] = []
        lock = asyncio.Lock()

        async def branch(name: str, other_plan: str | None) -> None:
            ws = await runner.branch(cp0)
            st = state[name] = {"status": "running", "attempts": [], "ws": ws, "plan": None, "files": {}}
            instr = ""
            if name == "B":
                instr = ("Branch B: propose a different approach from branch A." if not both_ways else
                         "Branch B: follow the generic review's view of this code; if it had no finding, leave the code "
                         "as is and add a test pinning the current behaviour.")
            inputs = {**base_inputs, "branch_instruction": instr, "other_plan": other_plan,
                      "_sim": {"branch": name, "findings": base_inputs["findings"], "originals": originals,
                               "both_ways": both_ways}}
            res = await self.gw.call("fix_plan", inputs, job_id=self.job.id if self.job else None, feature="fix",
                                     temperature=float(temps.get(name, 0.2)))
            plan = res.data
            st["plan"] = plan.get("plan")
            await self.emit("fix.plan", {"branch": name, "plan": plan.get("plan"), "model": res.model_id,
                                         "model_display": res.model_display, "latency_ms": res.latency_ms})
            cur = dict(originals)
            for it in range(1, int(fcfg["max_iterations"]) + 1):
                if self.job is not None and await self.job.cancelled():
                    st["status"] = "cancelled"
                    return
                if winner:
                    st["status"] = "stopped"
                    return
                attempt: dict[str, Any] = {"iteration": it, "step": "plan" if it == 1 else "repair",
                                           "plan_md": plan.get("plan"), "edits": plan.get("edits", []) + [
                                               {"new_file": n["path"]} for n in plan.get("new_files", [])],
                                           "model": {"model_id": res.model_id, "display": res.model_display,
                                                     "latency_ms": res.latency_ms}, "started_at": _now()}
                # read every file the plan touches from the workspace's current state
                for e in plan.get("edits", []):
                    if e.get("path") and e["path"] not in cur and E.safe_path(e["path"]):
                        cur[e["path"]] = await runner.read_file(ws, e["path"])
                changed, errs = E.apply(cur, plan, self.cfg.routing, fcfg["allowed_test_glob"])
                attempt["apply_errors"] = errs
                await self.emit("fix.apply", {"branch": name, "ok": not errs, "errors": errs})
                failure = ""
                if changed:
                    await runner.write_files(ws, [FileChange(p, t) for p, t in changed.items()])
                    cur.update(changed)
                    st["files"].update(changed)
                total_changed = sum(E.diff_stats(E.unified(p, originals.get(p), t))["changed_lines"]
                                    for p, t in st["files"].items())
                if total_changed > int(fcfg["max_changed_lines"]):
                    errs.append(f"the fix changes {total_changed} lines, more than {fcfg['max_changed_lines']}")
                if errs and not changed:
                    failure = "Apply errors:\n" + "\n".join(errs)
                    attempt["test"] = None
                else:
                    targets = [t for t in plan.get("tests_to_run", []) if t.startswith("tests/") and
                               (t in st["files"] or t in files_at_head)]
                    tr = await self.test(runner, ws, recipe, targets, name=name)
                    lint = await self.lint(runner, ws, recipe, st["files"], originals)
                    new_fail = [f for f in tr["failures"] if f["test"] not in run.baseline_failures]
                    ok = not new_fail and lint["errors"] == 0 and tr["tests"] > 0 and not errs
                    attempt["test"] = {"passed": tr["passed"], "failed": len(new_fail), "skipped": tr["skipped"],
                                       "errors": tr["errors"], "duration_ms": int(tr["time"] * 1000),
                                       "failures": [{"test": f["test"], "message": f["message"][:300]} for f in new_fail][:5],
                                       "lint_errors": lint["errors"], "ok": ok}
                    await self.emit("fix.test.result", {"branch": name, "passed": tr["passed"], "failed": len(new_fail),
                                                        "duration_ms": int(tr["time"] * 1000)})
                    if ok:
                        diff = "".join(E.unified(p, originals.get(p), t) for p, t in sorted(st["files"].items()))
                        vres = await self.gw.call("fix_verify", {
                            "finding": base_inputs["findings"][0], "diff": diff,
                            "test_summary": f"{tr['passed']} passed, {len(new_fail)} new failures",
                            "_sim": {"findings": base_inputs["findings"], "files": st["files"], "originals": originals}},
                            job_id=self.job.id if self.job else None, feature="fix")
                        attempt["verify"] = {**vres.data, "model": vres.model_display}
                        await self.emit("fix.verify", {"branch": name, "addresses_finding": vres.data["addresses_finding"],
                                                       "explanation": vres.data.get("explanation")})
                        if vres.data["addresses_finding"]:
                            attempt["finished_at"] = _now()
                            st["attempts"].append(attempt)
                            async with lock:
                                st["status"] = "passed"
                                st["diff"] = diff
                                st["passed_at"] = time.time()
                                if not winner:
                                    winner.append(name)
                            return
                        failure = "The tests pass but the change does not address the finding: " + \
                            vres.data.get("explanation", "")
                    else:
                        failure = self.failure_text(tr, new_fail, lint, errs)
                attempt["finished_at"] = _now()
                st["attempts"].append(attempt)
                if it >= int(fcfg["max_iterations"]):
                    break
                await self.emit("fix.repair", {"branch": name, "iteration": it + 1, "model": res.model_display})
                rinputs = {"plan": plan.get("plan", ""), "findings": base_inputs["findings"],
                           "current_diff": "".join(E.unified(p, originals.get(p), t) for p, t in sorted(st["files"].items())),
                           "failure": failure[: int(fcfg["repair"]["max_failure_chars"])],
                           "files": [{"path": p, "content": t} for p, t in sorted(cur.items()) if t is not None],
                           "_sim": {"branch": name, "failure": failure, "files": cur, "findings": base_inputs["findings"],
                                    "plan": plan, "iteration": it}}
                res = await self.gw.call("fix_repair", rinputs, job_id=self.job.id if self.job else None,
                                         feature="fix", temperature=float(temps.get(name, 0.2)))
                plan = res.data
            st["status"] = "failed"

        try:
            first = asyncio.create_task(branch("A", None))
            if len(names) > 1:
                await asyncio.sleep(0)
                # B gets A's plan text once A has planned
                for _ in range(200):
                    if state.get("A", {}).get("plan"):
                        break
                    await asyncio.sleep(0.05)
                second = asyncio.create_task(branch("B", state.get("A", {}).get("plan")))
                await asyncio.wait_for(asyncio.gather(first, second), timeout=int(fcfg["run_timeout_seconds"]))
            else:
                await asyncio.wait_for(first, timeout=int(fcfg["run_timeout_seconds"]))
        except TimeoutError:
            run.error = "The fix run took longer than allowed."
        except KeeperError as e:
            run.error = e.message
        passed = [n for n in names if state.get(n, {}).get("status") == "passed"]
        win = None
        if passed:
            same_cycle = [n for n in passed if abs(state[n]["passed_at"] - min(state[m]["passed_at"] for m in passed)) < 1]
            win = min(same_cycle, key=lambda n: (E.diff_stats(state[n]["diff"])["changed_lines"],
                                                 sum(1 for p in state[n]["files"] if originals.get(p) is None)))
        run.winning_branch = win
        run.status = "passed" if win else ("cancelled" if any(state.get(n, {}).get("status") == "cancelled"
                                                               for n in names) else "failed")
        run.diff = state[win]["diff"] if win else None
        run.diff_stats = E.diff_stats(run.diff) if run.diff else {}
        run.iterations = sum(len(state.get(n, {}).get("attempts", [])) for n in names)
        last = state[win]["attempts"][-1]["test"] if win else None
        run.junit_summary = {**run.junit_summary, "final": last}
        run.models = sorted({a["model"]["model_id"] for n in names for a in state.get(n, {}).get("attempts", [])
                             if a.get("model")})
        run.finished_at = datetime.now(UTC)
        run.cost_usd = round(float(self.job.cost_usd) if self.job else 0.0, 4)
        db.flush()
        for n in names:
            st = state.get(n)
            if not st:
                continue
            for a in st["attempts"]:
                db.add(M.FixAttempt(id=new_id("fxa"), fix_run_id=run.id, branch=n, iteration=a["iteration"],
                                    step=a["step"], model=(a.get("model") or {}).get("display"),
                                    latency_ms=(a.get("model") or {}).get("latency_ms"), plan_md=a.get("plan_md"),
                                    edits=a.get("edits", []), apply_errors=a.get("apply_errors", []),
                                    test_result={**(a.get("test") or {}), "verify": a.get("verify"),
                                                 "branch_status": st["status"],
                                                 "diff": st.get("diff") if n != win else None},
                                    started_at=_dt(a.get("started_at")), finished_at=_dt(a.get("finished_at"))))
            await runner.dispose(st["ws"])
        await runner.dispose(ws0)
        db.flush()
        await self.emit("fix.completed", {"status": run.status, "winning_branch": win, "diff_stats": run.diff_stats,
                                          "seconds": int(time.time() - t_start)})
        return run

    async def test(self, runner: Any, ws: Any, recipe: dict[str, Any], targets: list[str] | None,
                   name: str | None = None) -> dict[str, Any]:
        timeout = int(self.cfg.sandbox["test_timeout_seconds"])
        buf: list[str] = []
        last = [0.0]

        def out(chunk: str) -> None:
            buf.append(chunk)
            if self.job is not None and name and time.time() - last[0] > 0.25:
                last[0] = time.time()
                text = "".join(buf)
                buf.clear()
                asyncio.ensure_future(self.emit("fix.test.output", {"branch": name, "chunk": text[-2000:]}))
        if targets:
            cmd = RC.command(recipe, "test_targeted", python=ws.python, tests=targets)
            await runner.run(ws, cmd, timeout=timeout, on_output=out)
            t = junit.parse(ws.path / ".keeper" / "junit-targeted.xml")
            if t["failed"]:
                t["targeted_only"] = True
                return t
        cmd = RC.command(recipe, "test", python=ws.python)
        r = await runner.run(ws, cmd, timeout=timeout, on_output=out)
        res = junit.parse(ws.path / ".keeper" / "junit.xml")
        if res.get("missing"):
            res["failures"] = [{"test": "collection", "message": r.stdout_tail[-1500:], "text": r.stdout_tail[-4000:]}]
            res["failed"] = 1
        res["timed_out"] = r.timed_out
        res["output"] = r.stdout_tail[-4000:]
        return res

    async def lint(self, runner: Any, ws: Any, recipe: dict[str, Any], files: dict[str, str],
                   originals: dict[str, str | None]) -> dict[str, Any]:
        py = [p for p in files if p.endswith(".py")]
        if not py:
            return {"errors": 0, "items": []}
        cmd = RC.command(recipe, "lint", python=ws.python, files=py)
        r = await runner.run(ws, cmd, timeout=60)
        try:
            items = json.loads(r.stdout_tail[r.stdout_tail.find("["):]) if "[" in r.stdout_tail else []
        except json.JSONDecodeError:
            items = []
        errs = []
        for d in items:
            rel = d.get("filename", "")
            rel = rel.split(str(ws.path) + "/", 1)[-1]
            changed = E.changed_lines(originals.get(rel), files.get(rel, ""))
            if d.get("location", {}).get("row") in changed:
                errs.append({"path": rel, "line": d["location"]["row"], "code": d.get("code"), "message": d.get("message")})
        return {"errors": len(errs), "items": errs}

    @staticmethod
    def failure_text(tr: dict[str, Any], new_fail: list[dict[str, Any]], lint: dict[str, Any], errs: list[str]) -> str:
        parts = []
        if errs:
            parts.append("Apply errors:\n" + "\n".join(errs))
        if new_fail:
            f = new_fail[0]
            parts.append(f"{len(new_fail)} test(s) failed. First: {f['test']}\n{f['message']}\n{f.get('text', '')}")
        elif tr.get("tests", 0) == 0:
            parts.append("No tests ran.\n" + tr.get("output", "")[-2000:])
        if lint["errors"]:
            parts.append("New lint errors:\n" + "\n".join(f"{x['path']}:{x['line']} {x['code']} {x['message']}"
                                                         for x in lint["items"][:5]))
        return "\n\n".join(parts)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None

"""Process start and stop: logging, migrations, interrupted jobs, the runner and its handlers, the demo load,
the model probe and sandbox selection (docs/04-architecture/04 §1)."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select

from keeper.config import get_config, get_settings
from keeper.core.errors import Conflict, KeeperError, NotFound
from keeper.db import models as M
from keeper.db import repo as R
from keeper.db.session import session_scope
from keeper.jobs.runner import JobContext, get_runner, handler, mark_interrupted
from keeper.logging import get_logger
from keeper.services.common import current_version, lens_of, maintainer, project, pull

log = get_logger("keeper.startup")
_bg: list[asyncio.Task[Any]] = []


# --------------------------------------------------------------------------------------------- helpers
def _gw():  # type: ignore[no-untyped-def]
    from keeper.llm.gateway import get_gateway
    return get_gateway()


def _ruler(db, gw):  # type: ignore[no-untyped-def]
    from keeper.baseline.ruler import ensure
    return ensure(db, gw.model_for(get_config().baseline["llm"]["role"]))


async def _analyze(db, p: M.Project, n: int, job: JobContext) -> M.Analysis:  # type: ignore[no-untyped-def]
    from keeper.analysis.pipeline import analyze_pr
    gw = _gw()
    pr = pull(db, p, n)
    m = maintainer(db, p)
    lens = lens_of(db, p, m.id)
    lv = current_version(db, lens) if lens is not None and lens.status != "revoked" else None
    a = await analyze_pr(db, p, pr, gateway=gw, ruler=_ruler(db, gw), maintainer=m, lens_version=lv,
                         lens_paused=bool(lens and lens.status == "paused"), job=job)
    db.commit()
    return a


# --------------------------------------------------------------------------------------------- handlers
@handler("load_demo")
async def h_load_demo(job: JobContext) -> dict[str, Any]:
    from keeper.ingest.demo import load_demo

    def work() -> dict[str, Any]:
        with session_scope() as db:
            R.set_state(db, "load_demo", {"status": "running", "job_id": job.id})
        try:
            with session_scope() as db:
                p = load_demo(db, with_snapshot=bool(job.params.get("with_snapshot", True)))
                R.set_state(db, "loaded_at", datetime.now(UTC).isoformat())
                R.set_state(db, "load_demo", {"status": "done", "job_id": job.id})
                return {"project_id": p.id}
        except KeeperError as e:
            with session_scope() as db:
                R.set_state(db, "load_demo", {"status": "failed", "job_id": job.id, "error": e.message})
            raise
    await job.step("Loading the demo world", 1, 1)
    out = await asyncio.to_thread(work)
    from keeper.db.repo import invalidate_state_cache
    invalidate_state_cache()
    return out


@handler("triage")
async def h_triage(job: JobContext) -> dict[str, Any]:
    nums = list(job.params.get("numbers") or [])
    done = []
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        for i, n in enumerate(nums):
            if await job.cancelled():
                break
            await job.progress(i, len(nums), f"#{n}")
            a = await _analyze(db, p, int(n), job)
            done.append({"number": n, "lane": a.pr_lane})
            await job.event("triage.pr", {"pr_number": n, "lane": a.pr_lane, "done": i + 1, "total": len(nums)})
    return {"analysed": len(done), "lanes": done}


@handler("analyze")
async def h_analyze(job: JobContext) -> dict[str, Any]:
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        a = await _analyze(db, p, int(job.params["number"]), job)
        return {"analysis_id": a.id, "lane": a.pr_lane, "number": a.pr_number}


@handler("fix")
async def h_fix(job: JobContext) -> dict[str, Any]:
    from keeper.analysis.context import build_context
    from keeper.fix.runner import FixRunner
    gw = _gw()
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        pr = pull(db, p, int(job.params["number"]))
        findings, analysis = [], None
        for rid in job.params["finding_ids"]:
            rf = db.get(M.RoutedFindingRow, rid)
            if rf is None:
                raise NotFound("Finding not found.")
            analysis = analysis or db.get(M.Analysis, rf.analysis_id)
            f = db.get(M.FindingRow, rf.finding_id)
            findings.append({"id": rf.id, "category": f.category, "statement": f.statement, "user_text": rf.user_text,
                             "suggestion": f.suggestion, "anchor": {"path": f.path, "start_line": f.start_line}})
        head = analysis.head_sha if analysis else pr.head_sha
        diff_text = build_context(db, p, pr, head_sha=head)[0].diff_text
        run = await FixRunner(gw, job).run(db, p, pr, analysis, findings, branches=job.params.get("branches"),
                                           user_hint=job.params.get("user_hint"),
                                           both_ways=bool(job.params.get("both_ways")), diff_text=diff_text or "")
        run.finished_at = run.finished_at or datetime.now(UTC)
        db.commit()
        return {"fix_id": run.id, "status": run.status, "winning_branch": run.winning_branch}


@handler("handoff")
async def h_handoff(job: JobContext) -> dict[str, Any]:
    from keeper.analysis.context import build_context
    from keeper.analysis.pipeline import make_handoff
    from keeper.services import views as V
    gw = _gw()
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        pr = pull(db, p, int(job.params["number"]))
        a = V.current_analysis(db, p.id, pr, ("queue", "history"))
        if a is None:
            raise Conflict("Analyse this PR first.")
        ctx, _ = build_context(db, p, pr, head_sha=a.head_sha)
        h = await make_handoff(db, p, pr, a, ctx, V.signals_of(a), maintainer(db, p), gateway=gw, job_id=job.id)
        db.commit()
        tgt = db.get(M.Person, h.target_person_id) if h.target_person_id else None
        await job.event("handoff.ready", {"target": tgt.login if tgt else None})
        return {"handoff_id": h.id, "target": tgt.login if tgt else None}


async def _new_version(job: JobContext, reason: str) -> dict[str, Any]:
    from keeper.lens.build import build_lens_version
    from keeper.lens.learn import edge_map
    gw = _gw()
    with session_scope() as db:
        lens = db.get(M.Lens, job.params["lens_id"])
        if lens is None:
            raise NotFound("Lens not found.")
        p = db.get(M.Project, lens.project_id)
        pe = db.get(M.Person, lens.person_id)
        parent = current_version(db, lens)
        cutoff = p.demo_now or datetime.now(UTC)
        await job.step("Building the new lens version", 1, 2)
        lv = await build_lens_version(db, p, pe, cutoff=cutoff, ruler=_ruler(db, gw), reason=reason, gateway=gw,
                                      job=job, parent=parent)
        edge_map(db, p, pe, lv)
        for ev in db.execute(select(M.FeedbackEvent).where(M.FeedbackEvent.project_id == p.id,
                                                           M.FeedbackEvent.consumed_by_lens_version_id.is_(None),
                                                           M.FeedbackEvent.kind != "lane_override")).scalars():
            ev.consumed_by_lens_version_id = lv.id
        R.audit(db, "maintainer", "lens_version_built", "lens", lens.id, {"version": lv.version, "reason": reason,
                                                                          "user_reason": job.params.get("reason")})
        db.commit()
        await job.step("Done", 2, 2)
        await job.event("lens.version.ready", {"lens_id": lens.id, "version": lv.version})
        return {"lens_id": lens.id, "version": lv.version}


@handler("learn")
async def h_learn(job: JobContext) -> dict[str, Any]:
    if job.params.get("lens_id"):
        return await _new_version(job, "rebuild_new_reviews")
    from keeper.lens.learn import learn
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        out = await learn(db, p, gateway=_gw(), job=job)
        db.commit()
        return {"versions": out.get("versions", {}), "ruler": out.get("ruler")}


@handler("lens_update")
async def h_lens_update(job: JobContext) -> dict[str, Any]:
    return await _new_version(job, "feedback_update")


@handler("recalibrate")
async def h_recalibrate(job: JobContext) -> dict[str, Any]:
    return await _new_version(job, "recalibrate")


@handler("fidelity")
async def h_fidelity(job: JobContext) -> dict[str, Any]:
    from keeper.fidelity.run import run_fidelity
    gw = _gw()
    with session_scope() as db:
        p = project(db, job.params.get("project_id"))
        m = maintainer(db, p)
        lens = lens_of(db, p, m.id)
        lv = db.execute(select(M.LensVersion).where(M.LensVersion.lens_id == lens.id, M.LensVersion.version ==
                                                    int(job.params.get("lens_version") or 1))).scalars().first()
        if lv is None:
            raise NotFound("Lens version not found.")
        fr = await run_fidelity(db, p, m, lv, _ruler(db, gw), gateway=gw, job=job)
        db.commit()
        return {"run_id": fr.id, "pass": bool((fr.passes or {}).get("overall"))}


@handler("probe")
async def h_probe(job: JobContext) -> dict[str, Any]:
    from keeper.llm import probe
    res = await _gw().run_probe()
    probe.save(res)
    return {"models": {k: v.get("exists") for k, v in res.get("models", {}).items()}}


@handler("sandbox_check")
async def h_sandbox_check(job: JobContext) -> dict[str, Any]:
    from keeper.sandbox.select import select as select_sandbox
    runner, reason, want = await select_sandbox()
    return {"provider": runner.name, "requested": want, "reason": reason, "isolation": runner.isolation}


@handler("reset_live")
async def h_reset_live(job: JobContext) -> dict[str, Any]:
    from keeper.ingest.snapshot import TABLES
    n = 0
    with session_scope() as db:
        for t in reversed(TABLES):
            if "origin" in t.__table__.c:
                n += int(db.execute(delete(t).where(t.__table__.c.origin == "live")).rowcount or 0)
    return {"deleted": n}


@handler("import")
async def h_import(job: JobContext) -> dict[str, Any]:
    from keeper.sources.github.importer import run_import
    return await run_import(job)


# ------------------------------------------------------------------------------------------- lifecycle
def _needs_demo_load() -> bool:
    s = get_settings()
    f = s.data_dir / "manifest.json"
    if not f.exists():
        return False
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    with session_scope() as db:
        has = db.execute(select(M.Project.id).where(M.Project.kind == "demo")).first() is not None
        return not has or R.get_state(db, "manifest_sha") != sha


async def _probe_bg() -> None:
    from keeper.llm import probe
    gw = _gw()
    try:
        cached = probe.load_cached()
        if cached.get("models"):
            gw.probe = cached
        elif get_settings().live:
            probe.save(await gw.run_probe())
    except Exception as e:  # noqa: BLE001
        log.warning("model probe failed: %s", e)


async def _sandbox_bg() -> None:
    from keeper.sandbox.select import select as select_sandbox
    try:
        await select_sandbox()
    except Exception as e:  # noqa: BLE001
        log.warning("sandbox selection failed: %s", e)


async def on_startup() -> None:
    from keeper.db.__main__ import upgrade
    from keeper.logging import setup_logging
    s = get_settings()
    setup_logging(s.LOG_LEVEL, s.runtime_dir, s.log_format, s.secret_values())
    await asyncio.to_thread(upgrade)
    n = mark_interrupted()
    if n:
        log.info("marked %d interrupted jobs", n)
    runner = get_runner()
    runner.start()
    if _needs_demo_load():
        runner.submit("load_demo", {}, key="load_demo")
    loop = asyncio.get_event_loop()
    _bg.extend([loop.create_task(_probe_bg()), loop.create_task(_sandbox_bg())])


async def on_shutdown() -> None:
    from keeper.db import sidecar
    for t in _bg:
        t.cancel()
    await get_runner().stop()
    with contextlib.suppress(Exception):
        sidecar.flush(10)

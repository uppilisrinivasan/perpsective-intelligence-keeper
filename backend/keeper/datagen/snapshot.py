"""Build Keeper's saved analysis of the demo project (docs/03-data/06 §9, FR-DATA-4): load the demo world into a
temporary runtime, learn, analyse the live queue, run the demo fix, record the demo learner's practice and a few
Ask answers, then export everything to data/snapshots/<project>/ and refresh the manifest.

With LLM_PROVIDER=fake the snapshot is an offline simulation and says so (snapshot.json "simulated": true)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FIX_LANES = ("shared", "edge")


def _say(msg: str) -> None:
    print(f"  {msg}", flush=True)


async def _build(out_dir: Path) -> dict[str, Any]:
    from sqlalchemy import delete, select

    from keeper import __version__
    from keeper.app.deps import Ctx
    from keeper.assistant import loop
    from keeper.config import get_config, get_settings
    from keeper.core.timeutil import parse_ts
    from keeper.db import models as M
    from keeper.db import sidecar
    from keeper.db.__main__ import upgrade
    from keeper.db.session import session_scope
    from keeper.ingest import snapshot as SNAP
    from keeper.ingest.demo import DEMO_ID, load_demo, manifest
    from keeper.jobs.runner import get_runner
    from keeper.lens.learn import learn
    from keeper.llm.gateway import get_gateway
    from keeper.services import startup  # noqa: F401  (registers the job handlers)

    cfg = get_config()
    gw = get_gateway()
    t0 = time.time()
    upgrade()
    m = manifest()
    with session_scope() as db:
        load_demo(db, with_snapshot=False)
    _say(f"demo world loaded ({time.time() - t0:.0f} s)")
    with session_scope() as db:
        p = db.get(M.Project, DEMO_ID)
        out = await learn(db, p, gateway=gw, cutoff_v1=parse_ts(p.meta["cutoff_v1"]))
        db.commit()
    sidecar.flush(60)
    _say(f"lens learned and tested ({time.time() - t0:.0f} s)")
    runner = get_runner()
    with session_scope() as db:
        nums = sorted(n for (n,) in db.execute(select(M.Pull.number).where(M.Pull.project_id == DEMO_ID,
                                                                          M.Pull.state == "open")))
    _, res = await runner.run_inline("triage", {"project_id": DEMO_ID, "numbers": nums})
    if res.get("error"):
        raise RuntimeError(f"triage failed: {res['error']}")
    _say(f"live queue analysed: {len(nums)} PRs ({time.time() - t0:.0f} s)")
    # handoffs for every PR in the unknown lane that doesn't have one yet
    with session_scope() as db:
        unk = [a.pr_number for a in db.execute(select(M.Analysis).where(M.Analysis.project_id == DEMO_ID,
                                                                        M.Analysis.purpose == "queue",
                                                                        M.Analysis.pr_lane == "unknown")).scalars()
               if db.execute(select(M.Handoff.id).where(M.Handoff.analysis_id == a.id)).first() is None]
    for n in unk:
        await runner.run_inline("handoff", {"project_id": DEMO_ID, "number": n})
    # the demo fix
    fix_pr = (m.get("tour_hints") or {}).get("fix_demo")
    fix: dict[str, Any] = {}
    if fix_pr:
        with session_scope() as db:
            a = db.execute(select(M.Analysis).where(M.Analysis.project_id == DEMO_ID, M.Analysis.pr_number == fix_pr,
                                                    M.Analysis.purpose == "queue")).scalars().first()
            ids = []
            if a is not None:
                for rf in db.execute(select(M.RoutedFindingRow).where(M.RoutedFindingRow.analysis_id == a.id)).scalars():
                    f = db.get(M.FindingRow, rf.finding_id)
                    if rf.lane in FIX_LANES and rf.fixable and cfg.fixable(f.category):
                        ids.append((0 if rf.lane == "edge" else 1, rf.id))
        if ids:
            _, fix = await runner.run_inline("fix", {"project_id": DEMO_ID, "number": fix_pr,
                                                     "finding_ids": [i for _, i in sorted(ids)[:2]]})
            _say(f"demo fix on #{fix_pr}: {fix.get('status') or fix.get('error')} ({time.time() - t0:.0f} s)")
        else:
            _say(f"demo fix skipped: no fixable finding on #{fix_pr}")
    # the demo learner's practice (notes authored with the world; scored like any answer)
    notes_f = get_settings().data_dir / "sources" / "keeper" / "practice_notes.json"
    practice = {}
    if notes_f.exists():
        practice = await _practice(json.loads(notes_f.read_text()))
        _say(f"practice recorded: {practice}")
    # saved Ask answers
    ctx = Ctx(role="maintainer", request_id="snapshot", guest_key="snapshot")
    questions = list(cfg.ui["assistant"]["suggestions"]["default"])
    examples = []
    from keeper.app import schemas as S
    from keeper.services import chat
    for q in questions:
        th = chat.create_thread(S.ChatThreadCreate(context=None), ctx)
        cards: list[dict[str, Any]] = []
        text, steps = "", []
        async for ev in loop.answer(th.id, q, {}, ctx):
            d = json.loads(ev["data"])
            if ev["event"] == "chat.delta":
                text += d["text"]
            elif ev["event"] == "chat.card":
                cards.append(d["card"])
            elif ev["event"] == "chat.tool_step" and d["status"] != "running":
                steps.append({k: d.get(k) for k in ("name", "label", "status", "duration_ms")})
        examples.append({"id": f"ex{len(examples) + 1}", "question": q, "answer_md": text, "cards": cards,
                         "tool_trace": steps})
    _say(f"{len(examples)} Ask examples saved")
    sidecar.flush(60)
    # the Ask examples ship as chat_examples.jsonl; the threads that produced them are not saved results
    with session_scope() as db:
        db.execute(delete(M.ChatMessage))
        db.execute(delete(M.ChatThread))
    # export
    if out_dir.exists():
        shutil.rmtree(out_dir)
    with session_scope() as db:
        counts = SNAP.export(db, out_dir, DEMO_ID)
        models = sorted({c.model_id for c in db.execute(select(M.LLMCall)).scalars() if c.model_id})
    (out_dir / "chat_examples.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in examples),
                                                 encoding="utf-8")
    meta = {"created_at": datetime.now(UTC).isoformat(), "simulated": gw.fake, "models": models,
            "keeper_version": __version__, "ruler_id": out.get("ruler"), "counts": counts,
            "fix": {"pr": fix_pr, **{k: fix.get(k) for k in ("fix_id", "status")}}, "practice": practice}
    (out_dir / "snapshot.json").write_text(json.dumps(meta, indent=2, default=str) + "\n")
    return meta


async def _practice(spec: dict[str, Any]) -> dict[str, Any]:
    """Run the authored before/after sessions for the demo learner through the normal practice service."""
    from keeper.app import schemas as S
    from keeper.app.deps import Ctx
    from keeper.db import models as M
    from keeper.db.session import session_scope
    from keeper.services import practice as P

    login = spec["learner"]
    ctx = Ctx(role="contributor", request_id="snapshot", guest_key=f"person:{login}")
    out: dict[str, Any] = {}
    for kind in ("before", "learn", "after"):
        notes_by_pr = spec.get("sessions", {}).get(kind)
        if not notes_by_pr:
            continue
        nums = [int(n) for n in notes_by_pr]
        with session_scope() as db:
            p = db.execute(__import__("sqlalchemy").select(M.Project)).scalars().first()
            target = db.get(M.Person, p.primary_maintainer_id)
            from keeper.services.common import current_version, lens_of
            lv = current_version(db, lens_of(db, p, target.id))
            from keeper.growth import practice as PR
            s = PR.new_session(db, p, f"person:{login}", target, kind, nums, lv)
            sid = s.id
        for i, n in enumerate(nums):
            notes = [S.PracticeNote(**x) for x in notes_by_pr[str(n)]]
            fb = await P.submit_answer(sid, i, S.PracticeAnswerRequest(notes=notes), ctx)
            if fb.status == "hint":
                await P.submit_answer(sid, i, S.PracticeAnswerRequest(notes=notes), ctx)
        out[kind] = P.complete(sid, ctx).result.get("recall")
    return out


def run_snapshot(*, yes: bool = False) -> int:
    from keeper.config import get_settings, reset_settings
    from keeper.datagen.validate import write_manifest
    from keeper.db.session import reset_engine

    s = get_settings()
    if not s.live:
        print("✗ The snapshot needs model access: set NEBIUS_API_KEY in .env, or LLM_PROVIDER=fake for an offline "
              "simulation.", file=sys.stderr)
        return 3
    if s.LLM_PROVIDER != "fake" and not yes:
        print("This calls Nemotron for the whole demo (learn, Proof, the queue, a fix, practice, Ask): roughly a few "
              "dollars and a few hundred thousand tokens. Re-run with --yes to go ahead.")
        return 2
    data_dir = s.data_dir
    out_dir = data_dir / "snapshots" / "prj_demo"
    tmp = Path(tempfile.mkdtemp(prefix="keeper-snapshot-"))
    old = os.environ.get("KEEPER_RUNTIME_DIR")
    os.environ["KEEPER_RUNTIME_DIR"] = str(tmp)
    reset_settings()
    reset_engine()
    from keeper.llm import gateway as GW
    GW._gateway = None
    print(f"Building the snapshot in {tmp} ({'offline simulation' if s.LLM_PROVIDER == 'fake' else 'live models'})")
    t0 = time.time()
    try:
        meta = asyncio.run(_build(out_dir))
    finally:
        if old is None:
            os.environ.pop("KEEPER_RUNTIME_DIR", None)
        else:
            os.environ["KEEPER_RUNTIME_DIR"] = old
        reset_settings()
        reset_engine()
    m = json.loads((data_dir / "manifest.json").read_text())
    m.pop("files", None)
    m["models_used"] = {**m.get("models_used", {}), "snapshot": ", ".join(meta["models"]) or "none",
                        "snapshot_simulated": bool(meta["simulated"])}
    write_manifest(data_dir, m)
    shutil.rmtree(tmp, ignore_errors=True)
    size = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file()) / 1e6
    print(f"✓ Snapshot written to {out_dir} ({size:.1f} MB) in {time.time() - t0:.0f} s; manifest updated.")
    return 0

"""Practice: the learner's Growth Test (methodology 12 Part A). Before and after are unassisted; learn gives a hint
(where and what kind of thing, never the answer), a second try, then the reveal. Results never flatter."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.analysis.context import build_context, hunk_excerpt
from keeper.config import get_config
from keeper.core.types import Anchor, Finding, MatchPair
from keeper.db import models as M
from keeper.db import repo as R
from keeper.growth import forms as FM
from keeper.ids import new_id, stable_id
from keeper.lens.apply import load_items
from keeper.residual.candidates import candidates
from keeper.residual.match import anchor_text, assign


def target_findings(db: Session, project: M.Project, target: M.Person, pr: int) -> list[Finding]:
    return [f for f in R.findings(db, project.id, pr_number=pr, source="human", person_id=target.id,
                                  context="history") if f.substantive]


def item_bank(db: Session, project: M.Project, target: M.Person, lv: M.LensVersion | None,
              exclude: set[int] | None = None) -> list[dict[str, Any]]:
    cfg = get_config()
    p = cfg.growth["practice"]
    sev = {k: float(v["weight"]) for k, v in cfg.taxonomy["severities"].items()}
    pulls = db.execute(select(M.Pull).where(M.Pull.project_id == project.id, M.Pull.split == "holdout")
                       .order_by(M.Pull.number)).scalars().all()
    bank = []
    for pr in pulls:
        if exclude and pr.number in exclude:
            continue
        hs = target_findings(db, project, target, pr.number)
        if len(hs) < int(p["min_findings"]):
            continue
        head = hs[0].head_sha or pr.head_sha
        ctx, _ = build_context(db, project, pr, head_sha=head)
        if ctx.changed_lines > int(p["max_changed_lines"]):
            continue
        base = [f for f in R.findings(db, project.id, pr_number=pr.number, source="baseline", head_sha=head)]
        matched = set()
        for m in db.execute(select(M.ResidualSample).where(M.ResidualSample.pr_number == pr.number,
                                                           M.ResidualSample.person_id == target.id,
                                                           M.ResidualSample.klass == "shared")).scalars():
            matched.add(m.finding_id)
        fs = [{"severity": f.severity, "baseline_found": f.id in matched} for f in hs]
        bank.append({"pr": pr.number, "head": head, "difficulty": FM.difficulty(fs, sev),
                     "categories": [f.category for f in hs], "n": len(hs), "baseline": len(base)})
    FM.bucketize(bank)
    return bank


def cost_weights(db: Session, lv: M.LensVersion | None) -> dict[str, float]:
    if lv is None:
        return {}
    out = {}
    for it in load_items(db, lv.id):
        w = float(it.stats.get("cost_weight") or 0) or 1.0
        for fid in it.member_ids:
            out[fid] = max(out.get(fid, 0.0), w)
    return out


def note_findings(project: M.Project, pr: int, notes: list[dict[str, Any]], answer_id: str) -> list[Finding]:
    out = []
    for i, n in enumerate(notes):
        anchor = Anchor(scope="line", path=n["path"], start_line=n["line"], end_line=n["line"]) \
            if n.get("path") and n.get("line") else Anchor(scope="pr")
        out.append(Finding(id=stable_id("fnd", answer_id, i), project_id=project.id, pr_number=pr, source="learner",
                           anchor=anchor, category=n.get("category") or "correctness", severity="minor",
                           statement=n["text"].strip()[:600], substantive=True,
                           refs={"note_id": n.get("id") or f"n{i + 1}"}))
    return out


async def score(db: Session, project: M.Project, target: M.Person, pr: int, notes: list[dict[str, Any]],
                answer_id: str, lv: M.LensVersion | None, *, gateway: Any, job_id: str | None = None
                ) -> dict[str, Any]:
    cfg = get_config()
    hs = target_findings(db, project, target, pr)
    for i, n in enumerate(notes):
        n.setdefault("id", f"n{i + 1}")
    ls = note_findings(project, pr, notes, answer_id)
    # notes are short and unlabelled: pair every note with every finding of P on the same file or PR-wide
    pairs = candidates(ls, hs, {**cfg.matching, "min_lexical": 0.0, "max_candidates_per_finding": 6})
    res = await gateway.call("practice_score", {
        "findings": [{"id": f.id, "category": f.category, "path": f.anchor.path, "line": f.anchor.start_line,
                      "statement": f.statement} for f in hs],
        "notes": [{"id": n["id"], "path": n.get("path"), "line": n.get("line"), "text": n["text"]} for n in notes],
        "pairs": [{"pair_id": p["pair_id"], "note_id": p["a"].refs["note_id"], "finding_id": p["b"].id} for p in pairs],
        "_sim": {"pairs": [{"pair_id": p["pair_id"], "a": p["a"].model_dump(mode="json"),
                            "b": p["b"].model_dump(mode="json"), "lexical": p["lexical"], "anchor": p["anchor"]}
                           for p in pairs], "notes": notes,
                 "baseline": [f.model_dump(mode="json") for f in R.findings(db, project.id, pr_number=pr,
                                                                             source="baseline")]}},
        job_id=job_id, feature="practice")
    by_id = {p["pair_id"]: p for p in pairs}
    judged = [MatchPair(a_id=by_id[d["pair_id"]]["a"].id, b_id=by_id[d["pair_id"]]["b"].id, decision=d["decision"],
                        weight=float(cfg.matching["weights"].get(d["decision"], 0)), rationale=d.get("rationale", ""))
              for d in res.data.get("decisions", []) if d.get("pair_id") in by_id]
    m = assign(ls, hs, judged, cfg.matching["weights"])
    verdict = {d["note_id"]: d["verdict"] for d in res.data.get("feedback", [])}
    w = cost_weights(db, lv)
    thr = float(cfg.growth["practice"]["costly_threshold"])
    matched_h = {p.b_id: p for p in m.pairs}
    note_of = {f.id: f.refs["note_id"] for f in ls}
    caught = [{"note_id": note_of[p.a_id], "finding_id": p.b_id, "decision": p.decision} for p in m.pairs]
    missed = [f for f in hs if f.id not in matched_h]
    own = [n["id"] for n in notes if verdict.get(n["id"]) == "valid_other" and
           n["id"] not in {c["note_id"] for c in caught}]
    noise = [n["id"] for n in notes if verdict.get(n["id"]) == "not_an_issue" and
             n["id"] not in {c["note_id"] for c in caught}]
    total_w = sum(w.get(f.id, 1.0) for f in hs) or 1.0
    got_w = sum(w.get(f.id, 1.0) * p.weight for fid, p in matched_h.items() for f in hs if f.id == fid)
    return {"recall": round(m.matched_weight() / len(hs), 3) if hs else None, "n_target": len(hs),
            "matched": round(m.matched_weight(), 2), "costly_recall": round(got_w / total_w, 3),
            "costly_misses": [f.id for f in missed if w.get(f.id, 1.0) >= thr],
            "caught": caught, "missed": [f.id for f in missed], "own_eye": own, "noise": noise,
            "verdicts": verdict, "model": res.meta()}


async def hints(db: Session, project: M.Project, target: M.Person, pr_number: int, scored: dict[str, Any],
                notes: list[dict[str, Any]], lv: M.LensVersion | None, *, gateway: Any, job_id: str | None = None
                ) -> list[dict[str, Any]]:
    pr = db.execute(select(M.Pull).where(M.Pull.project_id == project.id, M.Pull.number == pr_number)).scalars().one()
    hs = {f.id: f for f in target_findings(db, project, target, pr_number)}
    ctx, _ = build_context(db, project, pr, head_sha=next(iter(hs.values())).head_sha if hs else None)
    out = []
    w = cost_weights(db, lv)
    thr = float(get_config().growth["practice"]["costly_threshold"])
    for fid in scored["missed"]:
        f = hs.get(fid)
        if f is None or w.get(fid, 1.0) < thr:
            continue
        res = await gateway.call("practice_coach", {"finding": {"statement": f.statement, "category": f.category,
                                                                "path": f.anchor.path, "line": f.anchor.start_line},
                                                    "hunk": hunk_excerpt(ctx, f.anchor.path, f.anchor.start_line, 8),
                                                    "notes": notes,
                                                    "_sim": {"finding": f.model_dump(mode="json")}},
                                 job_id=job_id, feature="practice")
        out.append({"text": res.data["hint"], "path": f.anchor.path})
    return out


def reveal(db: Session, project: M.Project, target: M.Person, pr_number: int, scored: dict[str, Any],
           notes: list[dict[str, Any]], lv: M.LensVersion | None) -> dict[str, Any]:
    hs = {f.id: f for f in target_findings(db, project, target, pr_number)}
    items = load_items(db, lv.id) if lv else []
    item_of = {fid: it for it in items for fid in it.member_ids}
    by_note = {n["id"]: n for n in notes}

    def fd(f: Finding) -> dict[str, Any]:
        rc = None
        if f.refs.get("comment_ids"):
            rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == f.refs["comment_ids"][0])
                            ).scalars().first()
        return {"id": f.id, "statement": f.statement, "category": f.category, "path": f.anchor.path,
                "line": f.anchor.start_line, "author": target.login, "comment": rc.body if rc else None,
                "html_url": rc.html_url if rc else None}

    return {"caught": [{"note_id": c["note_id"], "note": by_note.get(c["note_id"], {}).get("text"),
                        "finding": fd(hs[c["finding_id"]])} for c in scored["caught"] if c["finding_id"] in hs],
            "missed": [{"finding": fd(hs[fid]),
                        "why_it_matters_md": (item_of[fid].rationale or item_of[fid].statement) if fid in item_of else None,
                        "lens_item": {"id": item_of[fid].id, "title": item_of[fid].title,
                                      "support": item_of[fid].stats.get("support")} if fid in item_of else None}
                       for fid in scored["missed"] if fid in hs],
            "own_eye": [{"note_id": n, "note": by_note.get(n, {}).get("text"),
                         "why": "A real issue that wasn't raised in the review."} for n in scored["own_eye"]],
            "not_an_issue": [{"note_id": n, "note": by_note.get(n, {}).get("text"),
                              "line": by_note.get(n, {}).get("line")} for n in scored["noise"]]}


def session_result(answers: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """Sums over items; growth is computed by the caller against a matching before session."""
    n_t = sum(a["scored"]["n_target"] for a in answers if a.get("scored"))
    got = sum(a["scored"]["matched"] for a in answers if a.get("scored"))
    costly = sum(len(a["scored"]["costly_misses"]) for a in answers if a.get("scored"))
    own = sum(len(a["scored"]["own_eye"]) for a in answers if a.get("scored"))
    noise = sum(len(a["scored"]["noise"]) for a in answers if a.get("scored"))
    cr = [a["scored"]["costly_recall"] for a in answers if a.get("scored")]
    return {"kind": kind, "items": len(answers), "recall": round(got / n_t, 3) if n_t else None, "caught": got,
            "target_total": n_t, "costly_recall": round(sum(cr) / len(cr), 3) if cr else None,
            "costly_misses": costly, "own_eye": own, "noise": noise}


def new_session(db: Session, project: M.Project, learner_key: str, target: M.Person, kind: str, items: list[int],
                lv: M.LensVersion | None, origin: str = "live") -> M.PracticeSession:
    s = M.PracticeSession(id=new_id("prs"), project_id=project.id, learner_key=learner_key, target_person_id=target.id,
                          lens_version_id=lv.id if lv else None, kind=kind, item_pr_numbers=items, status="open",
                          origin=origin)
    db.add(s)
    db.flush()
    return s


_ = anchor_text

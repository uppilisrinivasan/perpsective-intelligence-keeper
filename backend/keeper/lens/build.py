"""L6 and L7: build an immutable lens version from a consenting person's residual, outcomes and a cutoff
(methodology 05 §3, 09). Statistics are computed by code; the deep model only names and describes clusters."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.cluster import AgglomerativeClustering
from sklearn.preprocessing import normalize
from sqlalchemy import select
from sqlalchemy.orm import Session

from keeper.analysis.context import parse_patch
from keeper.calibrate import bias as B
from keeper.calibrate import stats as ST
from keeper.config import get_config
from keeper.core.errors import ConsentRequired
from keeper.core.globs import area_of, match
from keeper.core.textsim import identifiers, tfidf_matrix, tokens
from keeper.core.types import Finding, LensItem, Triggers
from keeper.db import models as M
from keeper.db import repo as R
from keeper.ids import new_id, stable_id
from keeper.lens import card as CARD
from keeper.lens import digest as DIG
from keeper.lens.governance import active_consent
from keeper.outcomes.link import addressed

_ID = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+|[A-Za-z_][A-Za-z0-9_]{2,}")
_PY_NOISE = {"self", "def", "return", "import", "from", "None", "True", "False", "str", "int", "list", "dict",
             "for", "if", "else", "elif", "not", "and", "with", "raise", "class", "pass", "lambda", "while", "assert",
             "bool", "in", "is", "or", "as", "try", "except", "yield", "async", "await", "global", "continue",
             "break", "test", "tests", "pytest", "object", "Any", "Mapping", "Path", "path", "name", "line",
             "value", "text", "skip", "append", "doc", "base", "root", "skip.append"}


# ------------------------------------------------------------------------------------------------------ samples
def _hunk_for(db: Session, f: Finding, patches: dict[tuple[int, str], dict[str, str | None]], project: M.Project,
              pulls: dict[int, M.Pull], max_lines: int) -> str:
    """The diff around a finding's anchor: GitHub's diff_hunk for human comments, else the PR's patch at the head."""
    cids = f.refs.get("comment_ids") or []
    if cids:
        rc = db.execute(select(M.ReviewComment).where(M.ReviewComment.gh_id == cids[0])).scalars().first()
        if rc and rc.diff_hunk:
            return "\n".join(rc.diff_hunk.split("\n")[-max_lines:])
    if f.anchor.path is None:
        return ""
    pr = pulls.get(f.pr_number)
    if pr is None:
        return ""
    key = (pr.number, f.head_sha or pr.head_sha)
    if key not in patches:
        from keeper.analysis.context import pr_files
        patches[key] = {fc.path: fc.patch for fc in pr_files(db, project, pr, key[1])}
    patch = patches[key].get(f.anchor.path)
    if not patch:
        return ""
    _, _, _, hunks = parse_patch(patch)
    line = f.anchor.start_line
    for h in hunks:
        rows = h["lines"]
        idx = [i for i, (_, ln, _) in enumerate(rows) if line is not None and ln == line]
        if idx:
            i = idx[0]
            seg = rows[max(0, i - max_lines + 2): i + 2]
            return "\n".join(("+" if k == "+" else ("-" if k == "-" else " ")) + t for k, _, t in seg)
    if hunks:
        return "\n".join(("+" if k == "+" else " ") + t for k, _, t in hunks[0]["lines"][:max_lines] if k != "-")
    return ""


def code_tokens(hunk: str, exclude: frozenset[str] = frozenset()) -> list[str]:
    """Identifiers (dotted calls kept whole) on added and context lines; imports and docstrings skipped."""
    toks = []
    for ln in hunk.split("\n"):
        if not (ln.startswith("+") or ln.startswith(" ")):
            continue
        body = ln[1:].strip()
        if body.startswith(("import ", "from ", "#", '"""', "@@")):
            continue
        toks.extend(t for t in _ID.findall(body) if t not in _PY_NOISE and t.split(".")[0] not in exclude)
    return toks


def featurise(samples: list[dict[str, Any]], weights: dict[str, float]) -> np.ndarray:
    """Statement TF-IDF + category one-hot + path tokens + code tokens, each block L2-normalised and weighted."""
    if not samples:
        return np.zeros((0, 1))
    # code spans and numbers name the instance, not the concern: leave them out of the statement features
    stm, _ = tfidf_matrix([re.sub(r"`[^`]*`|#?\d+", " ", s["finding"].statement) for s in samples])
    cats = sorted({s["finding"].category for s in samples})
    cat = csr_matrix(np.array([[1.0 if s["finding"].category == c else 0.0 for c in cats] for s in samples]))
    paths, _ = tfidf_matrix([" ".join(re.split(r"[/_.]", (s["finding"].anchor.path or "pr").rsplit("/", 1)[0]))
                             for s in samples])
    code, _ = tfidf_matrix([" ".join(s["code"]) or "_none_" for s in samples])
    blocks = [normalize(stm) * float(weights["statement"]), normalize(cat) * float(weights["category"]),
              normalize(paths) * float(weights["path"]), normalize(code) * float(weights["code"])]
    return normalize(hstack(blocks)).toarray()


def cluster(X: np.ndarray, threshold: float) -> list[int]:
    if len(X) == 0:
        return []
    if len(X) == 1:
        return [0]
    model = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average",
                                    distance_threshold=threshold)
    return [int(x) for x in model.fit_predict(X)]


def _central(X: np.ndarray, idx: list[int], k: int) -> list[int]:
    sub = np.asarray(X[idx], dtype=np.float64)
    c = sub.mean(axis=0)
    # elementwise sum instead of matmul: Accelerate's BLAS on macOS raises spurious FP warnings here
    with np.errstate(all="ignore"):
        d = (sub * c).sum(axis=1) / (np.linalg.norm(sub, axis=1) * (np.linalg.norm(c) or 1) + 1e-9)
    d = np.nan_to_num(d)
    return [idx[i] for i in np.argsort(-d)[:k]]


def _group_of(cfg: dict[str, Any], category: str) -> str:
    for g, cats in cfg["build"]["category_groups"].items():
        if category in cats:
            return g
    return "other"


def _area_glob(paths: list[str]) -> list[str]:
    """Fallback path triggers: the common directories of the member paths."""
    dirs = Counter(p.rsplit("/", 1)[0] if "/" in p else p for p in paths if p)
    out = []
    for d, _ in dirs.most_common(3):
        out.append(f"{d}/*" if "/" in d or d.endswith(".toml") is False else d)
    return out or ["*"]


def validate_triggers(proposed: Triggers, members: list[dict[str, Any]], min_cov: float) -> Triggers:
    """Code checks the model's triggers against the cluster: globs must cover the members, patterns must compile
    and fire on enough member hunks (methodology 05 §3 step 4)."""
    paths = [m["finding"].anchor.path for m in members if m["finding"].anchor.path]
    globs = [g for g in proposed.paths if isinstance(g, str) and g and any(match(p, g) for p in paths)]
    cov = sum(1 for p in paths if any(match(p, g) for g in globs)) / max(1, len(paths))
    if cov < min_cov:
        globs = _area_glob(paths)
    pats = []
    hunks = [m["hunk"] for m in members]
    for p in proposed.code_patterns:
        try:
            rx = re.compile(p)
        except re.error:
            continue
        hit = sum(1 for h in hunks if h and rx.search(h)) / max(1, len(hunks))
        if hit >= 0.3:
            pats.append(p)
    if pats:
        union = sum(1 for h in hunks if h and any(re.search(p, h) for p in pats)) / max(1, len(hunks))
        if union < min_cov:
            pats = []
    return Triggers(paths=sorted(set(globs)), code_patterns=pats, pr_features=dict(proposed.pr_features))


# ------------------------------------------------------------------------------------------------------ firing
def item_fires(item: LensItem, files: list[str], added: dict[str, list[tuple[int, str]]],
               removed: dict[str, list[tuple[int, str]]] | None = None) -> tuple[bool, list[tuple[str, int]]]:
    """Methodology 06 §1a. Returns (fires, matched (path, line) positions)."""
    t = item.triggers
    globs = t.paths or []
    path_hit = [p for p in files if any(match(p, g) for g in globs)]
    hits: list[tuple[str, int]] = []
    rxs = []
    for p in t.code_patterns:
        try:
            rxs.append(re.compile(p))
        except re.error:
            continue
    counter = []
    for p in (t.pr_features or {}).get("counter_patterns", []) or []:
        try:
            counter.append(re.compile(p))
        except re.error:
            continue
    scan = dict(added)
    if removed and item.category == "api_compat":
        for k, v in removed.items():
            scan.setdefault(k, []).extend(v)
    for path, lines in scan.items():
        for ln, text in lines:
            if any(rx.search(text) for rx in rxs):
                hits.append((path, ln))
    if path_hit and not rxs:
        return True, [(p, (scan.get(p) or [(1, "")])[0][0]) for p in path_hit]
    if path_hit and any(h[0] in path_hit for h in hits):
        return True, [h for h in hits if h[0] in path_hit]
    if len(hits) >= 2:
        return True, hits
    return False, []


def counter_present(item: LensItem, added: dict[str, list[tuple[int, str]]], paths: list[str]) -> bool:
    pats = (item.triggers.pr_features or {}).get("counter_patterns", []) or []
    for p in pats:
        rx = re.compile(p)
        for path in paths:
            if any(rx.search(t) for _, t in added.get(path, [])):
                return True
    return False


# ------------------------------------------------------------------------------------------------------ building
async def build_lens_version(db: Session, project: M.Project, person: M.Person, *, cutoff: datetime,
                             ruler: M.Ruler, reason: str, gateway: Any, job: Any = None,
                             parent: M.LensVersion | None = None, origin: str = "live") -> M.LensVersion:
    cfg = get_config()
    lcfg = cfg.lens
    consent = active_consent(db, project.id, person.id)
    if consent is None:
        raise ConsentRequired(f"Keeper needs consent before building a lens for {person.login}.")
    lens = db.execute(select(M.Lens).where(M.Lens.project_id == project.id, M.Lens.person_id == person.id)
                      ).scalars().first()
    if lens is None:
        lens = M.Lens(id=stable_id("lns", project.id, person.id), person_id=person.id, project_id=project.id,
                      status="active", consent_id=consent.id, shared_in_project=True)
        db.add(lens)
        db.flush()
    if lens.status == "revoked":
        raise ConsentRequired("This lens was revoked; record consent again before rebuilding.")
    version = (db.execute(select(M.LensVersion.version).where(M.LensVersion.lens_id == lens.id)
                          .order_by(M.LensVersion.version.desc())).scalars().first() or 0) + 1
    lv = M.LensVersion(id=stable_id("lv", lens.id, version, cutoff.isoformat(), ruler.id), lens_id=lens.id,
                       version=version, cutoff_at=cutoff, ruler_id=ruler.id, change_reason=reason,
                       parent_version_id=parent.id if parent else None, status="building",
                       job_id=job.id if job else None, origin=origin)
    db.add(lv)
    db.flush()
    stage = (lambda s, d, t: job.event("lens.stage", {"stage": s, "done": d, "total": t})) if job else None

    pulls = {p.number: p for p in db.execute(select(M.Pull).where(M.Pull.project_id == project.id)).scalars()}
    train = {n for n, p in pulls.items() if p.created_at < cutoff and p.split != "live"}
    rows = db.execute(select(M.ResidualSample).where(M.ResidualSample.person_id == person.id,
                                                     M.ResidualSample.ruler_id == ruler.id)).scalars().all()
    rows = [r for r in rows if r.pr_number in train and (r.at is None or r.at < cutoff)]
    fids = {r.finding_id for r in rows} | {r.matched_finding_id for r in rows if r.matched_finding_id}
    frows = {f.id: R.from_row(f) for f in db.execute(select(M.FindingRow).where(M.FindingRow.id.in_(fids))).scalars()}
    patches: dict[tuple[int, str], dict[str, str | None]] = {}
    max_h = int(lcfg["build"]["max_hunk_lines"])

    def sample(r: M.ResidualSample) -> dict[str, Any] | None:
        f = frows.get(r.finding_id)
        if f is None:
            return None
        h = _hunk_for(db, f, patches, project, pulls, max_h)
        return {"id": r.id, "finding": f, "weight": r.weight, "klass": r.klass, "hunk": h, "code": code_tokens(h),
                "pr": r.pr_number, "evidence": r.evidence}

    r_plus = [s for r in rows if r.klass == "r_plus" and r.weight >= float(lcfg["build"]["min_sample_weight"])
              and (s := sample(r)) and s["finding"].substantive]
    r_minus = [s for r in rows if r.klass == "r_minus" and (s := sample(r)) and s["finding"].substantive]
    shared = [s for r in rows if r.klass == "shared" and (s := sample(r))]
    if stage:
        await stage("cluster", 0, 3)

    # P's own findings before the cutoff, for trigger precision, counter-examples and the digest
    own = [f for f in R.findings(db, project.id, source="human", person_id=person.id, context="history")
           if f.pr_number in train and (f.created_at is None or f.created_at < cutoff)]
    reviewed = sorted({f.pr_number for f in own})
    pr_ctx: dict[int, dict[str, Any]] = {}
    from keeper.analysis.context import pr_files
    first_head = {}
    for f in own:
        first_head.setdefault(f.pr_number, f.head_sha)
    for n in reviewed:
        files = pr_files(db, project, pulls[n], first_head.get(n) or pulls[n].head_sha)
        added = {fc.path: parse_patch(fc.patch)[0] for fc in files}
        removed = {fc.path: parse_patch(fc.patch)[1] for fc in files}
        pr_ctx[n] = {"files": [fc.path for fc in files], "added": added, "removed": removed,
                     "changed": sum(fc.additions + fc.deletions for fc in files)}

    items: list[LensItem] = []
    prev_items: dict[str, M.LensItemRow] = {}
    if parent is not None:
        for it in db.execute(select(M.LensItemRow).where(M.LensItemRow.lens_version_id == parent.id)).scalars():
            prev_items[it.stable_key] = it

    async def name_clusters(samples: list[dict[str, Any]], item_type: str) -> list[LensItem]:
        if not samples:
            return []
        by_group: dict[str, list[int]] = defaultdict(list)
        for i, s in enumerate(samples):
            by_group[_group_of(lcfg, s["finding"].category)].append(i)
        X = featurise(samples, lcfg["build"]["feature_weights"])
        out: list[LensItem] = []
        for g, idx in sorted(by_group.items()):
            labels = cluster(X[idx], float(lcfg["build"]["cluster_distance"]))
            groups: dict[int, list[int]] = defaultdict(list)
            for i, lab in zip(idx, labels, strict=False):
                groups[lab].append(i)
            real = {k: v for k, v in groups.items() if len(v) >= int(lcfg["build"]["min_cluster_size"])}
            misc = [i for k, v in groups.items() if k not in real for i in v]
            if not real:
                continue
            clusters = []
            cmap = {}
            for k, (_lab, members) in enumerate(sorted(real.items(), key=lambda kv: -len(kv[1]))):
                cid = f"c{k + 1}"
                cmap[cid] = members
                reps = _central(X, members, int(lcfg["build"]["max_representatives"]))
                refs = sorted({r for i in members for r in samples[i]["finding"].refs.get("history_refs", [])})
                clusters.append({"cluster_id": cid, "size": len(members),
                                 "paths": sorted({samples[i]["finding"].anchor.path or "(whole PR)" for i in members})[:8],
                                 "representatives": [{"sample_id": samples[i]["id"],
                                                      "statement": samples[i]["finding"].statement,
                                                      "path": samples[i]["finding"].anchor.path or "(whole PR)",
                                                      "hunk": samples[i]["hunk"]} for i in reps],
                                 "history_refs": [f"#{r}" for r in refs[:6]]})
            bg = Counter(t for i in idx for t in set(samples[i]["code"]))
            res = await gateway.call("lens_items", {
                "item_type": item_type, "group": g, "clusters": clusters,
                "misc": [{"sample_id": samples[i]["id"], "statement": samples[i]["finding"].statement,
                          "path": samples[i]["finding"].anchor.path or "(whole PR)"} for i in misc[:30]],
                "taxonomy": [{"id": k, "description": v["description"]} for k, v in cfg.taxonomy["categories"].items()],
                "_sim": {"clusters": [{"cluster_id": c["cluster_id"], "members": [
                    {"statement": samples[i]["finding"].statement, "category": samples[i]["finding"].category,
                     "path": samples[i]["finding"].anchor.path, "hunk": samples[i]["hunk"],
                     "code": samples[i]["code"], "severity": samples[i]["finding"].severity,
                     "refs": samples[i]["finding"].refs.get("history_refs", [])}
                    for i in cmap[c["cluster_id"]]]} for c in clusters], "item_type": item_type,
                    "background": {t: n / max(1, len(idx)) for t, n in bg.items()}}},
                job_id=job.id if job else None, feature="lens")
            id_of = {s["id"]: i for i, s in enumerate(samples)}
            used: set[str] = set()
            for d in res.data.get("items", []):
                cids = [c for c in d.get("cluster_ids", []) if c in cmap and c not in used]
                if not cids:
                    continue
                used.update(cids)
                members = sorted({i for c in cids for i in cmap[c]} - {id_of[x] for x in d.get("exclude_sample_ids", [])
                                                                       if x in id_of})
                members += [id_of[x] for x in d.get("attach_sample_ids", []) if x in id_of and id_of[x] in misc]
                if len(members) < 2:
                    continue
                msamples = [samples[i] for i in members]
                cat = Counter(s["finding"].category for s in msamples).most_common(1)[0][0]
                trig = validate_triggers(Triggers(paths=d["triggers"].get("paths", []),
                                                  code_patterns=d["triggers"].get("code_patterns", [])),
                                         msamples, float(lcfg["build"]["trigger_min_coverage"]))
                sev = Counter(s["finding"].severity for s in msamples).most_common(1)[0][0]
                member_ids = [s["finding"].id for s in msamples]
                skey = _stable_key(member_ids, prev_items, item_type, cat, float(lcfg["feedback"]["stable_id_jaccard"]),
                                   db)
                out.append(LensItem(id=stable_id("li", lv.id, skey), lens_version_id=lv.id, stable_key=skey,
                                    type=item_type, title=d["title"].strip()[:120], statement=d["statement"].strip(),
                                    rationale=d.get("rationale", ""), category=cat, severity_typical=sev,
                                    triggers=trig, member_ids=member_ids,
                                    provenance={"ruler_id": ruler.id, "build_job_id": job.id if job else None,
                                                "model_ids": [res.model_id], "llm_call_id": res.call_id}))
        return out

    edge_items = await name_clusters(r_plus, "edge")
    if stage:
        await stage("items", 1, 3)
    outcomes = db.execute(select(M.Outcome).where(M.Outcome.project_id == project.id)).scalars().all()
    bad_by_pr: dict[int, list[M.Outcome]] = defaultdict(list)
    for o in outcomes:
        if o.kind in ("reverted", "post_merge_bug", "follow_up_fix") and o.pr_number in train:
            bad_by_pr[o.pr_number].append(o)
    links = defaultdict(set)
    for lk, okind, opr in db.execute(select(M.OutcomeLink.finding_id, M.Outcome.kind, M.Outcome.pr_number)
                                     .join(M.Outcome).where(M.Outcome.project_id == project.id)):
        links[lk].add((okind, opr))
    merged_train = [n for n in train if pulls[n].merged_at is not None]
    window = int(cfg.matching["line_window"])

    def stats_for(it: LensItem, members: list[Finding]) -> dict[str, Any]:
        member_prs = {f.pr_number for f in members}
        fires_prs = [n for n in reviewed if item_fires(it, pr_ctx[n]["files"], pr_ctx[n]["added"],
                                                       pr_ctx[n]["removed"])[0]]
        flagged = [n for n in fires_prs if n in member_prs]
        prec = len(flagged) / len(fires_prs) if fires_prs else 0.0
        counter = sorted(set(fires_prs) - member_prs)
        # outcomes: concern present and ignored on merged PRs (P's member finding not addressed, or a baseline
        # finding of the item's category on the trigger files), then bad outcomes linked to those findings
        n_ign = k_bad = 0
        bad_linked: list[int] = []
        for f in members:
            pr = pulls[f.pr_number]
            if pr.merged_at is None:
                continue
            if not addressed(db, project, pr, f, window):
                n_ign += 1
                if links.get(f.id):
                    k_bad += 1
                    bad_linked.append(f.pr_number)
        touching = [n for n in merged_train if any(match(p, g) for p in (pr_ctx.get(n, {}).get("files") or
                                                                         [pf.filename for pf in []])
                                                   for g in it.triggers.paths)]
        base_rate = (sum(1 for n in touching if bad_by_pr.get(n)) / len(touching)) if touching else \
            (sum(1 for n in merged_train if bad_by_pr.get(n)) / max(1, len(merged_train)))
        post = ST.posterior(k_bad, n_ign, lcfg["calibration"]["prior"])
        dates = sorted(f.created_at for f in members if f.created_at)
        by_group: dict[str, dict[str, int]] = {}
        for n in fires_prs:
            assoc = pulls[n].author_association or "NONE"
            g = by_group.setdefault(assoc, {"fires": 0, "flags": 0})
            g["fires"] += 1
            g["flags"] += int(n in member_prs)
        sev_w = np.mean([float(lcfg["calibration"]["severity_weights"].get(f.severity, 1)) for f in members]) \
            if members else 1.0
        return {"support": len(members), "trigger_precision": round(prec, 3),
                "baseline_overlap": None, "fires": len(fires_prs), "flagged_prs": len(flagged),
                "outcome": {"bad_when_ignored": k_bad, "ignored": n_ign, "posterior_mean": round(post["posterior_mean"], 3),
                            "ci90": [round(x, 3) for x in post["ci90"]], "base_rate": round(base_rate, 3),
                            "lift": round(post["posterior_mean"] / base_rate, 2) if base_rate > 0 else None,
                            "bad_prs": sorted(set(bad_linked))},
                "first_seen": dates[0].date().isoformat() if dates else None,
                "last_seen": dates[-1].date().isoformat() if dates else None, "by_group": by_group,
                "cost_weight": round(ST.cost_weight(post["posterior_mean"], float(sev_w)), 3),
                "_counter": counter, "_fires": fires_prs}

    fmap = {f.id: f for f in own}
    for s in r_plus + r_minus + shared:
        fmap.setdefault(s["finding"].id, s["finding"])
    groups_cfg = lcfg["bias"]["groups"]
    group_of = {a: g for g, assocs in groups_cfg.items() for a in assocs}
    bias_rows: dict[str, dict[str, Any]] = {}
    for it in edge_items:
        members = [fmap[i] for i in it.member_ids if i in fmap]
        st = stats_for(it, members)
        it.counter_example_prs = st.pop("_counter")[:20]
        fires = st.pop("_fires")
        # counter patterns (code): identifiers frequent on counter-example PRs' trigger files and absent from the
        # members' trigger files — what the code looks like when this person had nothing to say
        member_tok: Counter[str] = Counter()
        for n in {f.pr_number for f in members}:
            if n not in pr_ctx:
                continue
            for p in pr_ctx[n]["files"]:
                if any(match(p, g) for g in it.triggers.paths):
                    member_tok.update(set(t for _, line in pr_ctx[n]["added"].get(p, []) for t in _ID.findall(line)
                                          if t not in _PY_NOISE))
        ctr_tok: Counter[str] = Counter()
        for n in it.counter_example_prs:
            for p in pr_ctx[n]["files"]:
                if any(match(p, g) for g in it.triggers.paths):
                    ctr_tok.update(set(t for _, line in pr_ctx[n]["added"].get(p, []) for t in _ID.findall(line)
                                       if t not in _PY_NOISE))
        ncnt = max(1, len(it.counter_example_prs))
        nmem = max(1, len({f.pr_number for f in members}))
        counter = [t for t, c in ctr_tok.most_common(20) if c / ncnt >= 0.5 and member_tok.get(t, 0) / nmem <= 0.1][:3]
        if counter:
            it.triggers.pr_features["counter_patterns"] = [rf"\b{re.escape(t)}\b" for t in counter]
        # bias: P flagging I by author group, stratified by size and area (only training PRs where I fires)
        brow = [{"group": group_of.get(pulls[n].author_association or "NONE", "regular"),
                 "flagged": n in {f.pr_number for f in members},
                 "size": B.size_bucket(pr_ctx[n]["changed"], lcfg["bias"]["size_buckets"]),
                 "area": area_of(next(iter(pr_ctx[n]["files"]), "(root)"), 2)} for n in fires]
        orows = [{"group": group_of.get(pulls[f.pr_number].author_association or "NONE", "regular"),
                  "bad": bool(links.get(f.id))} for f in members
                 if pulls[f.pr_number].merged_at and not addressed(db, project, pulls[f.pr_number], f, window)]
        bc = B.check_item(brow, lcfg, orows)
        bias_rows[it.id] = bc
        prev = prev_items.get(it.stable_key)
        if prev is not None and prev.status == "disabled_by_owner":
            it.status = "disabled_by_owner"
        elif prev is not None and prev.owner_override == "keep" and bc["verdict"] == "bias_suspected":
            it.status = ST.edge_status(st, lcfg, bias_flagged=False)
            it.owner_override = "keep"
        else:
            it.status = ST.edge_status(st, lcfg, bias_flagged=bc["verdict"] == "bias_suspected")
        if st["last_seen"] and (cutoff.date() - datetime.fromisoformat(st["last_seen"]).date()).days > \
                int(lcfg["status"]["retire_after_days"]) and it.status not in ("disabled_by_owner",):
            it.status = "retired"
        it.stats = st
        it.exemplar_ids = _exemplars(members, int(lcfg["build"]["max_exemplars"]))
        items.append(it)

    # blind spots: R− clusters with outcome evidence
    bs_items = await name_clusters(r_minus, "blind_spot")
    for it in bs_items:
        members = [fmap[i] for i in it.member_ids if i in fmap]
        st = stats_for(it, members)
        st.pop("_counter")
        st.pop("_fires")
        st["support"] = len(members)
        it.stats = st
        it.exemplar_ids = _exemplars(members, int(lcfg["build"]["max_exemplars"]))
        if ST.blind_spot_ok(st, lcfg):
            it.status = "validated"
            items.append(it)
    # shared ground: (category, top-level path) cells where generic review matches most of what P raises
    cells: dict[tuple[str, str], list[str]] = defaultdict(list)
    for s in r_plus + shared:
        f = s["finding"]
        top = (f.anchor.path or "").split("/")[0] or "(whole PR)"
        cells[(f.category, top)].append(s["klass"])
    tax = cfg.taxonomy["categories"]
    for (cat, top), klasses in cells.items():
        n = len(klasses)
        share = klasses.count("shared") / n
        if n >= int(lcfg["build"]["shared_min_findings"]) and share >= float(lcfg["build"]["shared_min_overlap"]):
            skey = f"shared:{cat}:{top}"
            label = tax.get(cat, {}).get("label", cat)
            items.append(LensItem(id=stable_id("li", lv.id, skey), lens_version_id=lv.id, stable_key=skey,
                                  type="shared_ground", title=lcfg.get("shared_ground_title", "{label} in {area}")
                                  .format(label=label, area=top), statement=lcfg.get(
                                      "shared_ground_statement", "Generic review already catches most {label_lc} "
                                      "concerns here ({share:.0%} of {n}).").format(label_lc=label.lower(), share=share,
                                                                                   n=n),
                                  category=cat, triggers=Triggers(paths=[f"{top}/*" if top != "(whole PR)" else "*"]),
                                  status="validated", stats={"support": n, "baseline_overlap": round(share, 3)},
                                  provenance={"ruler_id": ruler.id, "build_job_id": job.id if job else None,
                                              "model_ids": []}))
    if stage:
        await stage("calibrate", 2, 3)
    # calibration explanations (deep model writes words only; it never changes statuses)
    for it in items:
        if it.type == "shared_ground":
            continue
        o = it.stats.get("outcome") or {}
        prev = prev_items.get(it.stable_key)
        changed = prev is None or prev.status != it.status or abs(
            float((prev.stats or {}).get("outcome", {}).get("ci90", [0, 0])[1]) - float(o.get("ci90", [0, 0])[1])) > \
            float(lcfg["calibration"]["notes_ci_change"])
        if not changed or not o.get("ignored"):
            continue
        titles = [pulls[n].title for n in o.get("bad_prs", []) if n in pulls]
        res = await gateway.call("calibration_notes", {
            "item": {"title": it.title, "type": it.type, "status": it.status},
            "numbers": {"n_ignored": o.get("ignored"), "k_bad": o.get("bad_when_ignored"),
                        "hit_rate": o.get("posterior_mean"), "ci90": o.get("ci90"), "base_rate": o.get("base_rate"),
                        "support": it.stats.get("support")}, "outcome_titles": titles,
            "_sim": {"item": it.model_dump(mode="json"), "bad_prs": o.get("bad_prs", [])}},
            job_id=job.id if job else None, feature="lens")
        it.stats["explanation"] = res.data.get("explanation")
    # history digest, style hints and the card
    digest = DIG.build(own, items)
    lv.digest = digest
    lv.digest_sha = hashlib.sha256(digest.encode()).hexdigest()
    lv.style_hints = style_hints(db, project, person, cutoff)
    card_data, card_meta = await CARD.generate(items, person, gateway=gateway, job=job, include_bias=True)
    lv.card = card_data
    lv.card_md = CARD.render(card_data, person)
    for it in items:
        db.add(M.LensItemRow(id=it.id, lens_version_id=lv.id, stable_key=it.stable_key, type=it.type, title=it.title,
                             statement=it.statement, rationale=it.rationale, category=it.category,
                             severity_typical=it.severity_typical, triggers=it.triggers.model_dump(),
                             stats=it.stats, status=it.status, owner_override=it.owner_override,
                             owner_edits=list(prev_items[it.stable_key].owner_edits or []) if it.stable_key in prev_items
                             else [], explanation=it.stats.get("explanation"), provenance=it.provenance))
    db.flush()
    for it in items:
        for fid in it.member_ids:
            db.add(M.LensItemEvidence(lens_item_id=it.id, finding_id=fid, role="member"))
        for fid in it.exemplar_ids:
            db.add(M.LensItemEvidence(lens_item_id=it.id, finding_id=fid, role="exemplar"))
        for n in it.counter_example_prs:
            db.add(M.LensItemEvidence(lens_item_id=it.id, pr_number=n, role="counter_example"))
        if it.id in bias_rows:
            bc = bias_rows[it.id]
            db.add(M.BiasCheck(lens_item_id=it.id, odds_ratio=bc["odds_ratio"], ci_low=bc["ci_low"],
                               ci_high=bc["ci_high"], n_by_group=bc["n_by_group"], outcome_check=bc["outcome_check"],
                               verdict=bc["verdict"]))
    db.flush()
    accepted = db.execute(select(M.ResidualSample).where(M.ResidualSample.person_id == person.id,
                                                         M.ResidualSample.evidence != "review")).scalars().all()
    lv.build_stats = {"samples": {"r_plus": len(r_plus), "r_minus": len(r_minus), "shared": len(shared)},
                      "items": dict(Counter(i.type for i in items)), "statuses": dict(Counter(i.status for i in items)),
                      "reviewed_prs": len(reviewed), "findings": len(own), "retro_applied_prs": 0,
                      "accepted_suggestion_samples": len(accepted),
                      "period": {"from": min((f.created_at for f in own if f.created_at), default=cutoff).isoformat(),
                                 "to": cutoff.isoformat()}, "card": card_meta}
    lv.models = sorted({m for it in items for m in it.provenance.get("model_ids", [])} | set(card_meta.get("models", [])))
    lv.status = "ready"
    db.flush()
    R.audit(db, "system", "lens_build", "lens_version", lv.id, {"version": version, "reason": reason,
                                                                  "items": len(items)})
    if stage:
        await stage("card", 3, 3)
    return lv


def _exemplars(members: list[Finding], k: int) -> list[str]:
    """The most representative members, preferring different paths and recent ones."""
    seen_paths: set[str] = set()
    out = []
    for f in sorted(members, key=lambda f: (f.created_at or datetime.min.replace(tzinfo=None)), reverse=True):
        p = f.anchor.path or "(pr)"
        if p in seen_paths and len(out) < k // 2:
            continue
        seen_paths.add(p)
        out.append(f.id)
        if len(out) >= k:
            break
    return out


def _stable_key(member_ids: list[str], prev: dict[str, M.LensItemRow], item_type: str, category: str,
                min_jaccard: float, db: Session) -> str:
    """Keep item identity across versions when cluster membership overlaps enough (Jaccard)."""
    mine = set(member_ids)
    best, best_j = None, 0.0
    for key, row in prev.items():
        if row.type != item_type:
            continue
        theirs = {e.finding_id for e in db.execute(select(M.LensItemEvidence).where(
            M.LensItemEvidence.lens_item_id == row.id, M.LensItemEvidence.role == "member")).scalars()}
        if not theirs:
            continue
        j = len(mine & theirs) / len(mine | theirs)
        if j > best_j:
            best, best_j = key, j
    if best and best_j >= min_jaccard:
        return best
    return f"{item_type}:{category}:{hashlib.sha256(','.join(sorted(mine)).encode()).hexdigest()[:8]}"


def style_hints(db: Session, project: M.Project, person: M.Person, cutoff: datetime) -> dict[str, Any]:
    """Format habits for review drafts only (never used for fidelity): length, suggestions, questions, greetings."""
    rc = db.execute(select(M.ReviewComment.body).where(M.ReviewComment.author_id == person.id,
                                                       M.ReviewComment.created_at < cutoff)).scalars().all()
    rb = db.execute(select(M.Review.body).where(M.Review.reviewer_id == person.id)).scalars().all()
    bodies = [b for b in rc if b] + [b for b in rb if b]
    if not bodies:
        return {}
    lens_ = sorted(len(b.split()) for b in bodies)
    return {"median_words": lens_[len(lens_) // 2], "suggestion_share": round(sum("```suggestion" in b for b in bodies)
                                                                                / len(bodies), 2),
            "question_share": round(sum(b.strip().endswith("?") for b in bodies) / len(bodies), 2),
            "greeting_share": round(sum(b.lower().startswith(("thanks", "thank you")) for b in rb if b)
                                    / max(1, len([b for b in rb if b])), 2),
            "nit_prefix": any(b.lower().startswith("nit:") for b in bodies)}


def tokens_of(text: str) -> list[str]:
    return tokens(text)


_ = identifiers, new_id

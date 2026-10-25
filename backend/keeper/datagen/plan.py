"""G3: the plan. Code only, seeded: which PRs, issues and events exist, their order and dates, authors and
reviewers, which concern slots each PR contains, who flags them, what is addressed, how PRs end, and what
reality answers later (bugs, reverts, follow-up fixes). docs/03-data/06-synthetic-data-generation.md §4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from keeper.core.timeutil import iso, parse_ts
from keeper.datagen.codegen import AREA_SLOTS, CODE_AREAS, RENAMES
from keeper.datagen.world import World

SEVERITY = {"E1": "major", "E2": "major", "E3": "major", "E4": "minor", "E5": "major", "E6": "minor",
            "E7": "major", "E8": "major", "S1": "minor", "S2": "nit", "S3": "minor", "S4": "major", "B1": "minor",
            "B2": "minor", "X1": "minor", "D1": "minor", "T1": "major", "T2": "major", "T3": "major", "T4": "major",
            "U1": "major"}
CODE_TOGGLES = {"E1", "E2", "E4", "E5", "E6", "E7", "E8", "S1", "S2", "S3", "S4", "B1", "B2", "D1", "T3"}
MAINTAINER_SLOTS = {"E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "S1", "S2", "S3", "S4", "B1", "B2", "X1", "D1"}


@dataclass
class Person:
    key: str
    login: str
    name: str
    role: str
    gh_id: int
    tz: str = "UTC"
    member: bool = False
    first_pr_at: str | None = None


@dataclass
class PRPlan:
    key: str
    author: str
    intent: str
    kind: str
    area: str
    created_at: datetime
    noun: str | None = None
    number: int = 0
    slots: list[dict[str, Any]] = field(default_factory=list)
    target: str | None = None          # module key for modify-type PRs
    module: str | None = None          # module key this PR creates
    renames: dict[str, str] = field(default_factory=dict)
    rounds: list[dict[str, Any]] = field(default_factory=list)
    end: dict[str, Any] = field(default_factory=dict)
    outcome: dict[str, Any] | None = None
    association: str = "CONTRIBUTOR"
    split: str = "train"
    slop_traits: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    expected_lane: str | None = None
    expected_handoff: str | None = None
    live_key: str | None = None

    def slot_ids(self) -> list[str]:
        return [s["slot"] for s in self.slots]

    def to_json(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["created_at"] = iso(self.created_at)
        d["rounds"] = [{k: (iso(v) if isinstance(v, datetime) else v) for k, v in r.items()} for r in self.rounds]
        d["end"] = {k: (iso(v) if isinstance(v, datetime) else v) for k, v in self.end.items()}
        if self.outcome:
            d["outcome"] = {k: (iso(v) if isinstance(v, datetime) else v) for k, v in self.outcome.items()}
        return d


@dataclass
class IssuePlan:
    key: str
    kind: str                 # bug | feature | question
    author: str
    created_at: datetime
    number: int = 0
    slot: str | None = None
    culprit: str | None = None
    closed_at: datetime | None = None
    closed_by: str | None = None   # PR key
    labels: list[str] = field(default_factory=list)
    title_idx: int = 0

    def to_json(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["created_at"] = iso(self.created_at)
        d["closed_at"] = iso(self.closed_at)
        return d


class Planner:
    def __init__(self, w: World):
        self.w = w
        self.sc = w.scenario
        self.rng = np.random.Generator(np.random.PCG64(w.seed + 3))
        tl = self.sc["timeline"]
        self.end = parse_ts(tl["end"])
        self.months = int(tl["months"])
        self.start = self.end - timedelta(days=30.44 * self.months)
        self.cutoff = self.end - timedelta(days=30.44 * int(tl["holdout_months"]))
        self.people: dict[str, Person] = {}
        self.prs: list[PRPlan] = []
        self.issues: list[IssuePlan] = []
        self.modules: dict[str, dict[str, Any]] = {}   # module key → state on main
        self.busy: dict[str, datetime] = {}            # file/module key → busy until
        self.nouns_used: dict[str, set[str]] = {}
        self._k = 0
        self.away = [(self.month_start(a["start_month"]),
                      self.month_start(a["start_month"]) + timedelta(weeks=a["weeks"])) for a in tl["maintainer_away"]]

    # ------------------------------------------------------------------ helpers
    def month_start(self, m: float) -> datetime:
        return self.start + timedelta(days=30.44 * m)

    def month_of(self, t: datetime) -> float:
        return (t - self.start).total_seconds() / 86400 / 30.44

    def maintainer_away(self, t: datetime) -> bool:
        return any(a <= t < b for a, b in self.away)

    def chance(self, p: float) -> bool:
        return bool(self.rng.random() < p)

    def lognormal_days(self, median: float, p90: float) -> float:
        sigma = max(0.1, math.log(max(p90, median * 1.01) / median) / 1.2816)
        return float(median * math.exp(self.rng.normal(0, sigma)))

    def workday(self, t: datetime, tz_offset_hours: int = 1) -> datetime:
        """Move t to business hours (08–18 local) on a weekday."""
        local = t + timedelta(hours=tz_offset_hours)
        while local.weekday() >= 5:
            local += timedelta(days=1)
        if not 8 <= local.hour < 18:
            local = local.replace(hour=int(self.rng.integers(8, 18)), minute=int(self.rng.integers(0, 60)))
        return local - timedelta(hours=tz_offset_hours)

    def key(self, prefix: str) -> str:
        self._k += 1
        return f"{prefix}{self._k:04d}"

    def pick(self, items: list[Any], p: list[float] | None = None) -> Any:
        idx = int(self.rng.choice(len(items), p=p))
        return items[idx]

    # ------------------------------------------------------------------ people
    def make_people(self) -> None:
        wp = self.w.world["people"]
        ids = iter(sorted(self.rng.choice(np.arange(1_200_000, 98_000_000), size=400, replace=False).tolist()))

        def add(key: str, d: dict[str, Any], role: str) -> None:
            self.people[key] = Person(key=key, login=d["login"], name=d["name"], role=role, gh_id=int(next(ids)),
                                      tz=d.get("timezone", "UTC"))

        add("maintainer", wp["maintainer"], "maintainer")
        add("security", wp["security_reviewer"], "security_reviewer")
        for i, d in enumerate(wp["occasional_reviewers"]):
            add(f"occ{i}", d, "occasional")
        add("newcomer", wp["trusted_newcomer"], "newcomer")
        add("learner", wp["learner"], "learner")
        self.people["bot"] = Person(key="bot", login=wp["bot"]["login"], name=wp["bot"]["name"], role="bot",
                                    gh_id=int(next(ids)))
        members = set(self.w.world.get("members", []))
        for d in wp["contributors"]:
            add(f"c:{d['login']}", d, "contributor")
            self.people[f"c:{d['login']}"].member = d["login"] in members
        deny = {ln.strip().lower() for ln in (self.w.dir / "denylist.txt").read_text().splitlines()
                if ln.strip() and not ln.startswith("#")}
        taken = {p.login for p in self.people.values()}
        db = self.w.world["drive_by"]
        pairs = [(f, la) for f in db["first"] for la in db["last"]]
        order = self.rng.permutation(len(pairs))
        n = 0
        for i in order:
            f, la = pairs[int(i)]
            login = f"{f}-{la}{int(self.rng.integers(1, 99))}"
            if login in taken or f in deny:
                continue
            taken.add(login)
            self.people[f"d:{login}"] = Person(key=f"d:{login}", login=login, name=f"{f.title()} {la.upper()}.",
                                               role="driveby", gh_id=int(next(ids)))
            n += 1
            if n >= 110:
                break

    def contributor_for(self, t: datetime, *, first_time: bool | None = None) -> str:
        """Pick a PR author. About 40% of PRs come from first-time contributors (mostly one-off authors)."""
        mix = self.sc["people"]["contributors"]["association_mix"]
        want_first = first_time if first_time is not None else self.chance(mix["FIRST_TIME_CONTRIBUTOR"]
                                                                          + mix.get("NONE", 0))
        if want_first:
            fresh = [p for p in self.people.values() if p.role == "driveby" and p.first_pr_at is None]
            if fresh:
                return self.pick(fresh).key
        regulars = [p for p in self.people.values() if p.role in ("contributor", "learner")]
        prolific = set(self.w.world.get("prolific", []))
        weights = np.array([4.0 if p.login in prolific else 1.0 for p in regulars])
        return regulars[int(self.rng.choice(len(regulars), p=weights / weights.sum()))].key

    def association(self, author: str, t: datetime) -> str:
        p = self.people[author]
        if p.role == "maintainer":
            return "OWNER"
        if p.role == "security_reviewer" or p.member:
            return "MEMBER"
        if p.role == "bot":
            return "NONE"
        if p.first_pr_at is None or parse_ts(p.first_pr_at) >= t:
            p.first_pr_at = iso(t) if p.first_pr_at is None or parse_ts(p.first_pr_at) > t else p.first_pr_at
            if p.role == "driveby" and (self.w.seed + p.gh_id) % 9 == 0:
                return "NONE"
            return "FIRST_TIME_CONTRIBUTOR"
        return "CONTRIBUTOR"

    # ------------------------------------------------------------------ slots
    def sample_slots(self, area: str, intent: str, t: datetime, kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        allowed = AREA_SLOTS.get(area, set())
        for s in self.sc["concern_slots"]:
            sid = s["id"]
            if sid in ("X1", "U1", "T4", "E3", "T1", "T2"):
                continue
            if sid not in allowed:
                continue
            if kind == "modify" and sid in ("S1", "T3"):
                continue  # a rewrite keeps the module's tests; recursion limits come with new code only
            if sid == "E7" and (kind != "modify" or area not in RENAMES):
                continue
            if sid == "E5" and self.month_of(t) < float(s.get("history_anchor", {}).get("revert_month", 0)) + 0.6:
                continue  # the cache history the maintainer cites must already exist
            if kind == "feature" and sid == "E7":
                continue
            rate = min(0.95, float(s.get("presence_rate", 0)) * float(self.sc["prs"].get("presence_intensity", 1.0)))
            if self.chance(rate):
                d = {"slot": sid}
                if sid == "E1":
                    d["variant"] = self.pick(s["variants"])
                out.append(d)
        ids = {d["slot"] for d in out}
        if "B1" in ids and "B2" in ids:
            out = [d for d in out if d["slot"] != "B1"]
        # at most max_slots_per_pr planted slots, keeping the rarer edge and blind-spot slots first
        rank = {"E": 0, "B": 1, "T": 1, "D": 2, "S": 3}
        out.sort(key=lambda d: (rank.get(d["slot"][0], 4), self.rng.random()))
        return out[: int(self.sc["prs"]["max_slots_per_pr"])]

    # ------------------------------------------------------------------ reviews
    def reviewers_for(self, pr: PRPlan) -> list[str]:
        t = pr.created_at
        revs: list[str] = []
        away = self.maintainer_away(t + timedelta(days=2))
        if not away and self.chance(float(self.sc["prs"]["maintainer_review_share"])):
            revs.append("maintainer")
        shares = self.sc["people"]["security_reviewer"]["reviews_share_in_areas"]
        if pr.area in shares and self.chance(float(shares[pr.area])):
            revs.append("security")
        if not revs or self.chance(float(self.sc["people"]["occasional_reviewers"]["reviews_share"])):
            revs.append(self.pick(["occ0", "occ1"]))
        return [r for r in revs if r != pr.author]

    def flags(self, reviewer: str, pr: PRPlan, at: datetime) -> list[dict[str, Any]]:
        role = self.people[reviewer].role
        out = []
        newcomer = pr.association in ("FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE")
        for d in pr.slots:
            sid = d["slot"]
            s = self.w.slot(sid)
            owner = s.get("owner")
            if role == "maintainer" and sid in MAINTAINER_SLOTS:
                if sid == "D1" and self.month_of(at) < float(s.get("starts_month", 0)):
                    continue
                if sid == "X1":
                    fr = s["flag_rate_by_group"]["newcomer" if newcomer else "regular"]
                else:
                    fr = float(s.get("flag_rate", 0))
            elif role == "security_reviewer" and (owner == "security_reviewer" or sid == "E1"):
                fr = float(s.get("flag_rate", 0)) if owner == "security_reviewer" else 0.8
                if sid == "E1":
                    sid = "T4"
            elif role == "occasional" and owner == "any":
                fr = 0.35
            else:
                continue
            if self.chance(fr):
                out.append({"slot": sid, "severity": SEVERITY.get(sid, "minor"), "planted": d["slot"]})
        return out

    def plan_reviews(self, pr: PRPlan) -> None:
        """Rounds of review, author fix-ups and the end of the PR (merged or closed)."""
        reviewers = self.reviewers_for(pr)
        t = pr.created_at
        addressed: set[str] = set()
        remaining = list(pr.slots)
        lat = self.sc["prs"]["review_latency_days"]
        rounds_kind = self.pick(["one", "two", "three_plus"],
                                [self.sc["prs"]["rounds"][k] for k in ("one", "two", "three_plus")])
        max_rounds = {"one": 2, "two": 2, "three_plus": 3}[rounds_kind]
        flagged_any: dict[str, list[dict[str, Any]]] = {}
        for rnd in range(max_rounds):
            t = t + timedelta(days=self.lognormal_days(float(lat["median"]), float(lat["p90"])) * (0.6 if rnd else 1))
            round_flags: list[dict[str, Any]] = []
            for r in reviewers:
                at = self.workday(t + timedelta(minutes=int(self.rng.integers(0, 240))))
                cand = PRPlan(**{**pr.__dict__, "slots": [d for d in remaining if d["slot"] not in addressed]})
                fl = [] if rnd and self.chance(0.6) else self.flags(r, cand, at)
                fl = [f for f in fl if f["planted"] not in {x["planted"] for x in flagged_any.get(r, [])}]
                flagged_any.setdefault(r, []).extend(fl)
                round_flags.extend(fl)
                major = any(f["severity"] in ("major", "blocker") for f in fl)
                state = "CHANGES_REQUESTED" if major else ("COMMENTED" if fl else "APPROVED")
                social = int(self.rng.integers(0, 2)) if state == "APPROVED" else int(self.chance(0.25))
                pr.rounds.append({"type": "review", "reviewer": r, "at": at, "state": state, "findings": fl,
                                  "social": social, "question": bool(self.chance(0.12)) and not fl,
                                  "body": bool(fl) or self.chance(0.4), "shallow": state == "APPROVED" and
                                  not social and self.chance(0.5)})
            if not round_flags:
                break
            fix_at = t + timedelta(hours=float(self.rng.uniform(4, 60)))
            addr = [f["planted"] for f in round_flags if self.chance(float(self.sc["prs"]["address_rate"]))]
            if pr.kind == "slop":
                addr = []
            if addr:
                addressed |= set(addr)
                pr.rounds.append({"type": "fixup", "at": fix_at, "addresses": sorted(set(addr)),
                                  "replies": [f["planted"] for f in round_flags]})
            t = fix_at
        # approvals after the last fix-up
        last = pr.rounds[-1] if pr.rounds else None
        if last is None or last["type"] == "fixup" or last.get("state") != "APPROVED":
            t = t + timedelta(days=self.lognormal_days(0.8, 3))
            approver = next((r for r in reviewers if r == "maintainer"), reviewers[0] if reviewers else "maintainer")
            pr.rounds.append({"type": "review", "reviewer": approver, "at": self.workday(t), "state": "APPROVED",
                              "findings": [], "social": 1, "question": False, "body": False, "shallow": False})
        limit = self.end - timedelta(days=2)
        if any(r["at"] > limit for r in pr.rounds):
            pr.rounds = [r for r in pr.rounds if r["at"] <= limit]
            addressed = {a for r in pr.rounds if r["type"] == "fixup" for a in r["addresses"]}
            flagged_any = {k: [f for f in v if any(f in r.get("findings", []) for r in pr.rounds)]
                           for k, v in flagged_any.items()}
        pr.extra["addressed"] = sorted(addressed)
        pr.extra["flagged"] = sorted({f["planted"] for fl in flagged_any.values() for f in fl})
        last_at = pr.rounds[-1]["at"] if pr.rounds else pr.created_at + timedelta(days=1)
        end_t = min(last_at + timedelta(minutes=int(self.rng.integers(3, 90))), self.end - timedelta(days=1))
        merger = "maintainer" if not self.maintainer_away(end_t) else "security"
        flagged_e3 = "E3" in pr.extra["flagged"] and "E3" not in addressed
        if pr.kind == "slop":
            # a red CI blocks the merge, so only slop without failing tests can be merged
            if "failing_tests" not in pr.slop_traits and self.chance(float(self.sc["prs"]["slop"]["merged_share"])):
                pr.end = {"kind": "merged", "at": end_t, "by": merger}
            else:
                pr.rounds = [r for r in pr.rounds if r["type"] == "review"][:1]
                for r in pr.rounds:
                    r.update({"state": "COMMENTED", "findings": [], "social": 0, "body": False})
                pr.end = {"kind": "closed", "at": pr.created_at + timedelta(days=self.lognormal_days(2, 6)),
                          "by": "maintainer", "reason": "slop"}
        elif flagged_e3:
            pr.end = {"kind": "closed", "at": end_t, "by": "maintainer", "reason": "dependency"}
        elif self.chance(0.07) and pr.kind in ("feature", "modify"):
            pr.end = {"kind": "closed", "at": min(end_t + timedelta(days=30), self.end - timedelta(days=1)),
                      "by": "maintainer", "reason": "stale"}
        else:
            pr.end = {"kind": "merged", "at": end_t, "by": merger}

    # ------------------------------------------------------------------ outcomes
    def plan_outcome(self, pr: PRPlan) -> None:
        if pr.end.get("kind") != "merged" or pr.kind in ("revert", "outcome_fix"):
            return
        merged = pr.end["at"]
        ignored = [d["slot"] for d in pr.slots if d["slot"] not in pr.extra.get("addressed", [])]
        outcome = None
        for sid in ignored:
            s = self.w.slot(sid)
            for kind, p in (s.get("outcome_if_ignored") or {}).items():
                if self.chance(float(p)):
                    outcome = {"kind": kind, "cause_slot": sid}
                    break
            if outcome:
                break
        if outcome is None and pr.kind in ("feature", "modify") and self.chance(float(self.sc["outcomes"]["base_bad_rate"])):
            outcome = {"kind": "post_merge_bug", "cause_slot": None}
        if outcome is None:
            return
        o = self.sc["outcomes"]
        if outcome["kind"] == "reverted":
            delay = self.lognormal_days(float(o["revert_delay_days"]["median"]), float(o["revert_delay_days"]["p90"]))
        elif outcome["kind"] == "follow_up_fix":
            delay = self.lognormal_days(25, 60)
        else:
            delay = self.lognormal_days(float(o["bug_delay_days"]["median"]), float(o["bug_delay_days"]["p90"]))
        at = merged + timedelta(days=max(0.5, delay))
        if at > self.end - timedelta(days=6):
            return
        outcome["at"] = at
        pr.outcome = outcome
        if pr.module or pr.target:
            self.busy[pr.module or pr.target] = at + timedelta(days=8)

    # ------------------------------------------------------------------ PR construction
    def new_noun(self, area: str) -> str:
        pool = self.w.world["feature_nouns"].get(area, ["extra"])
        used = self.nouns_used.setdefault(area, set())
        free = [n for n in pool if n not in used]
        if free:
            n = self.pick(free)
        else:
            base = self.pick(pool)
            k = 2
            while f"{base}{k}" in used:
                k += 1
            n = f"{base}{k}"
        used.add(n)
        return n

    def target_module(self, area: str, t: datetime, *, need_renames: bool = False) -> str | None:
        cands = [k for k, m in self.modules.items() if m["area"] == area and m["merged_at"] is not None
                 and m["merged_at"] < t and not m.get("reverted") and self.busy.get(k, t) <= t
                 and (not need_renames or not m.get("renamed"))]
        return self.pick(sorted(cands)) if cands else None

    def add_pr(self, pr: PRPlan, *, review: bool = True) -> PRPlan:
        """Add a PR and plan its reviews, end and outcome right away, so later PRs see what has merged."""
        pr.association = self.association(pr.author, pr.created_at)
        self.prs.append(pr)
        if review and pr.split != "live" and not pr.extra.get("anchor") and pr.kind not in ("revert", "outcome_fix"):
            self.plan_reviews(pr)
            self.after_end(pr)
        return pr

    def after_end(self, pr: PRPlan) -> None:
        if pr.module and pr.end.get("kind") == "merged":
            self.modules[pr.module]["merged_at"] = pr.end["at"]
            self.busy[pr.module] = pr.end["at"]
        if pr.target and pr.end.get("kind") in ("merged", "closed"):
            self.busy[pr.target] = pr.end["at"]
            if pr.renames and pr.end.get("kind") == "merged":
                self.modules[pr.target]["renamed"] = True
        self.plan_outcome(pr)

    def feature_pr(self, t: datetime, area: str, author: str | None = None, *, slots: list[dict[str, Any]] | None = None,
                   intent: str = "feature", kind: str = "feature") -> PRPlan:
        noun = self.new_noun(area)
        mkey = f"m:{area}:{noun}"
        pr = PRPlan(key=self.key("PR"), author=author or self.contributor_for(t), intent=intent, kind=kind,
                    area=area, created_at=t, noun=noun, module=mkey)
        pr.slots = slots if slots is not None else self.sample_slots(area, intent, t, "feature")
        if kind == "feature" and area in CODE_AREAS and not any(d["slot"] == "S1" for d in pr.slots):
            pr.slots.append({"slot": "X1", "eligible": True})
        self.modules[mkey] = {"area": area, "noun": noun, "pr": pr.key, "merged_at": None}
        self.busy[mkey] = t + timedelta(days=40)
        return pr

    def modify_pr(self, t: datetime, area: str, intent: str, author: str | None = None,
                  slots: list[dict[str, Any]] | None = None) -> PRPlan | None:
        want_e7 = slots is not None and any(d["slot"] == "E7" for d in slots)
        target = self.target_module(area, t, need_renames=want_e7)
        if target is None:
            return None
        pr = PRPlan(key=self.key("PR"), author=author or self.contributor_for(t), intent=intent,
                    kind="modify", area=area, created_at=t, target=target, noun=self.modules[target]["noun"])
        if slots is None:
            slots = self.sample_slots(area, intent, t, "modify") if intent in ("refactor", "bugfix") else []
            if intent == "refactor" and area in RENAMES and self.chance(float(self.w.slot("E7")["presence_rate"])):
                slots = [{"slot": "E7"}] + [d for d in slots if d["slot"] != "E7"][:2]
        pr.slots = slots
        if intent in ("bugfix", "refactor") and not any(d["slot"] == "X1" for d in pr.slots):
            pr.slots.append({"slot": "X1", "eligible": True})  # changed branches with tests: eligible for X1
        if any(d["slot"] == "E7" for d in pr.slots):
            pr.renames = dict(RENAMES[area])
        self.busy[target] = t + timedelta(days=40)
        return pr

    def plan_history(self) -> None:
        sc = self.sc["prs"]
        total = int(sc["history_total"])
        primary = int(round(total * 0.84))
        intents = sc["intents"]
        aw = sc["area_weights"]
        areas = [a for a in aw if a in CODE_AREAS or a in ("build", "docs")]
        area_p = np.array([aw[a] for a in areas], dtype=float)
        area_p /= area_p.sum()
        quiet = float(sc.get("history_quiet_days", 6))  # history PRs all end before demo_now
        span = (self.end - self.start).days - quiet - 5
        growth = float(sc.get("activity_growth", 1.0))  # density rises linearly: the project gets busier
        u = self.rng.uniform(0, 1, size=primary)
        frac = (np.sqrt(1 + growth * (2 + growth) * u) - 1) / growth if growth > 0 else u
        times = sorted(self.start + timedelta(days=5 + float(x) * span) for x in frac)
        anchor = self.w.slot("E5")["history_anchor"]
        u1 = self.w.slot("U1")["history_events"][0]
        slop_share = sc["slop"]["share_by_month"]
        newcomer_prs = 0
        newcomer_start = self.month_start(self.sc["people"]["trusted_newcomer"]["first_pr_month"])
        for t in times:
            t = self.workday(t, 0)
            m = self.month_of(t)
            # history anchors
            if anchor and m >= anchor["pr_month"] and "cache_pr" not in self.__dict__:
                self.cache_pr = self.feature_pr(t, "loader", slots=[{"slot": "E5"}])
                self.cache_pr.extra["anchor"] = "cache"
                self.add_pr(self.cache_pr, review=False)
                continue
            if m >= u1["month"] and "u1_pr" not in self.__dict__:
                self.u1_pr = PRPlan(key=self.key("PR"), author=self.contributor_for(t, first_time=False),
                                    intent="build_ci", kind="build", area="build", created_at=t,
                                    slots=[{"slot": "U1"}], extra={"build": "release_fetch", "anchor": "u1"})
                self.add_pr(self.u1_pr, review=False)
                continue
            # slop
            share = next(v for k, v in slop_share.items() if int(k.split("-")[0]) <= m < int(k.split("-")[1]) + 1) \
                if any(int(k.split("-")[0]) <= m < int(k.split("-")[1]) + 1 for k in slop_share) else 0.0
            if self.chance(float(share)):
                area = self.pick([a for a in areas if a in CODE_AREAS])
                pr = self.feature_pr(t, area, author=self.contributor_for(t, first_time=True), kind="slop")
                pr.slop_traits = self.slop_traits()
                pr.slots = [d for d in pr.slots if d["slot"].startswith("S")][:2]
                self.add_pr(pr)
                continue
            if t >= newcomer_start and newcomer_prs < int(self.sc["people"]["trusted_newcomer"]["small_good_prs"]) \
                    and self.chance(0.3):
                newcomer_prs += 1
                area = self.pick(["docs", "cli", "parser"])
                pr = (self.docs_pr(t, "newcomer") if area == "docs"
                      else self.feature_pr(t, area, author="newcomer", slots=[]))
                self.add_pr(pr)
                continue
            intent = self.pick(list(intents), [intents[k] / sum(intents.values()) for k in intents])
            area = self.pick(areas, list(area_p))
            pr = self.make_intent_pr(t, intent, area)
            if pr is not None:
                self.add_pr(pr)

    def slop_traits(self) -> list[str]:
        traits = ["generic_description"]
        for tr in ("unused_helper", "hallucinated_api", "unrelated_changes", "failing_tests"):
            if self.chance(0.5):
                traits.append(tr)
        return traits

    def docs_pr(self, t: datetime, author: str | None = None) -> PRPlan:
        topic_i = int(self.rng.integers(0, len(self.w.world["pr_text"]["docs_topics"])))
        return PRPlan(key=self.key("PR"), author=author or self.contributor_for(t), intent="docs", kind="docs",
                      area="docs", created_at=t, extra={"topic": topic_i, "docs_file": f"docs/{self.docs_file(topic_i)}"})

    def docs_file(self, i: int) -> str:
        return ["includes.md", "interpolation.md", "format.md", "cli.md", "writing.md", "errors.md"][i % 6]

    def make_intent_pr(self, t: datetime, intent: str, area: str) -> PRPlan | None:
        if intent == "docs" or area == "docs":
            return self.docs_pr(t)
        if intent in ("build_ci",) or area == "build":
            return self.build_pr(t)
        if intent == "deps":
            return self.deps_pr(t, area if area in CODE_AREAS else "loader")
        if area not in CODE_AREAS:
            area = "loader"
        if intent == "feature":
            return self.feature_pr(t, area)
        pr = self.modify_pr(t, area, intent)
        return pr or self.feature_pr(t, area)

    def build_pr(self, t: datetime, author: str | None = None, *, slots: list[dict[str, Any]] | None = None,
                 change: str | None = None) -> PRPlan:
        if slots is None:
            slots = []
            for sid in ("T1", "T2"):
                if self.chance(float(self.w.slot(sid)["presence_rate"])):
                    slots.append({"slot": sid})
        change = change or self.pick(["ci_python", "ci_cache", "release_checksums", "fixtures_regen"])
        if any(d["slot"] == "T2" for d in slots):
            change = "binary_fixture"
        if any(d["slot"] == "T1" for d in slots) and change != "binary_fixture":
            change = "release_fetch"
        return PRPlan(key=self.key("PR"), author=author or self.contributor_for(t, first_time=False),
                      intent="build_ci", kind="build", area="build", created_at=t, slots=slots, extra={"build": change})

    def deps_pr(self, t: datetime, area: str, *, runtime: bool | None = None, author: str | None = None,
                extra_slots: list[dict[str, Any]] | None = None) -> PRPlan:
        pkgs = __import__("yaml").safe_load((self.w.dir / "real_packages.yaml").read_text())["packages"]
        pkg = self.pick(pkgs)
        rt = self.chance(float(self.w.slot("E3")["presence_rate"])) if runtime is None else runtime
        pr = self.feature_pr(t, area, author=author, slots=[], intent="deps", kind="deps")
        pr.slots = ([{"slot": "E3"}] if rt else []) + (extra_slots or [])
        pr.extra.update({"dep": pkg["name"], "dep_version": pkg["version"], "purpose": pkg["purpose"], "runtime": rt})
        return pr

    # ------------------------------------------------------------------ outcomes → future PRs and issues
    def realise_outcomes(self) -> None:
        for pr in list(self.prs):
            if not pr.outcome:
                continue
            o = pr.outcome
            if o["kind"] == "post_merge_bug":
                reporter = self.contributor_for(o["at"], first_time=self.chance(0.4))
                iss = IssuePlan(key=self.key("IS"), kind="bug", author=reporter, created_at=o["at"],
                                slot=o["cause_slot"], culprit=pr.key, labels=["bug"])
                self.issues.append(iss)
                fix_t = self.workday(o["at"] + timedelta(days=float(self.rng.uniform(1, 6))))
                fix = self.outcome_fix_pr(pr, fix_t, "bugfix", issue=iss)
                if fix is None:
                    continue
                iss.closed_by = fix.key
            elif o["kind"] == "reverted":
                rv = PRPlan(key=self.key("PR"), author="maintainer" if not self.maintainer_away(o["at"]) else "security",
                            intent="revert", kind="revert", area=pr.area, created_at=self.workday(o["at"]),
                            target=pr.key, noun=pr.noun)
                rv.rounds = []
                rv.end = {"kind": "merged", "at": rv.created_at + timedelta(minutes=int(self.rng.integers(10, 120))),
                          "by": rv.author}
                rv.association = self.association(rv.author, rv.created_at)
                self.prs.append(rv)
                o["revert_pr"] = rv.key
            elif o["kind"] == "follow_up_fix":
                self.outcome_fix_pr(pr, self.workday(o["at"]), "follow_up")

    def outcome_fix_pr(self, culprit: PRPlan, t: datetime, mode: str, issue: IssuePlan | None = None) -> PRPlan | None:
        mod = culprit.module or culprit.target
        if mod is None:
            return None
        author = self.pick(["maintainer", self.contributor_for(t, first_time=False)]) if mode == "bugfix" \
            else self.contributor_for(t, first_time=False)
        pr = PRPlan(key=self.key("PR"), author=author, intent="bugfix", kind="outcome_fix", area=culprit.area,
                    created_at=t, target=mod, noun=culprit.noun,
                    extra={"fixes_slot": culprit.outcome.get("cause_slot") if culprit.outcome else None,
                           "culprit": culprit.key, "issue": issue.key if issue else None, "mode": mode})
        pr.association = self.association(author, t)
        reviewer = "maintainer" if author != "maintainer" else self.pick(["occ0", "security"])
        rt = self.workday(t + timedelta(hours=float(self.rng.uniform(3, 30))))
        pr.rounds = [{"type": "review", "reviewer": reviewer, "at": rt, "state": "APPROVED", "findings": [],
                      "social": 1, "question": False, "body": False, "shallow": False}]
        pr.end = {"kind": "merged", "at": rt + timedelta(minutes=20), "by": "maintainer"
                  if not self.maintainer_away(rt) else "security"}
        self.prs.append(pr)
        if issue is not None:
            issue.closed_at = pr.end["at"]
        culprit.outcome["fix_pr"] = pr.key
        return pr

    def plan_anchor_events(self) -> None:
        """E5's history: the cache PR (month 9), the race bug (month 10), the revert (month 10)."""
        if "cache_pr" not in self.__dict__:
            return
        pr = self.cache_pr
        pr.rounds = [{"type": "review", "reviewer": "maintainer", "at": self.workday(pr.created_at + timedelta(days=2)),
                      "state": "APPROVED", "findings": [], "social": 1, "question": False, "body": False,
                      "shallow": False}]
        pr.end = {"kind": "merged", "at": pr.rounds[0]["at"] + timedelta(minutes=30), "by": "maintainer"}
        anchor = self.w.slot("E5")["history_anchor"]
        it = self.workday(max(self.month_start(anchor["issue_month"]), pr.end["at"] + timedelta(days=9)))
        iss = IssuePlan(key=self.key("IS"), kind="bug", author=self.contributor_for(it, first_time=False),
                        created_at=it, slot="E5", culprit=pr.key, labels=["bug"])
        self.issues.append(iss)
        rv = PRPlan(key=self.key("PR"), author="maintainer", intent="revert", kind="revert", area="loader",
                    created_at=self.workday(it + timedelta(days=2)), target=pr.key, noun=pr.noun)
        rv.end = {"kind": "merged", "at": rv.created_at + timedelta(minutes=40), "by": "maintainer"}
        rv.association = "OWNER"
        self.prs.append(rv)
        iss.closed_by = rv.key
        iss.closed_at = rv.end["at"]
        pr.outcome = {"kind": "reverted", "cause_slot": "E5", "at": rv.created_at, "revert_pr": rv.key,
                      "issue": iss.key}
        self.anchor = {"cache_pr": pr.key, "race_issue": iss.key, "revert_pr": rv.key}
        self.modules[pr.module]["reverted"] = True

    def plan_u1_events(self) -> None:
        if "u1_pr" not in self.__dict__:
            return
        pr = self.u1_pr
        at = self.workday(pr.created_at + timedelta(days=1.5))
        pr.rounds = [{"type": "review", "reviewer": "maintainer", "at": at, "state": "APPROVED", "findings": [],
                      "social": 1, "question": False, "body": False, "shallow": False}]
        pr.end = {"kind": "merged", "at": at + timedelta(minutes=25), "by": "maintainer"}
        rv_at = self.workday(pr.end["at"] + timedelta(days=self.lognormal_days(4, 12)))
        rv = PRPlan(key=self.key("PR"), author="security", intent="revert", kind="revert", area="build",
                    created_at=rv_at, target=pr.key)
        rv.end = {"kind": "merged", "at": rv_at + timedelta(minutes=50), "by": "maintainer"}
        rv.association = "MEMBER"
        self.prs.append(rv)
        pr.outcome = {"kind": "reverted", "cause_slot": "U1", "at": rv_at, "revert_pr": rv.key}

    # ------------------------------------------------------------------ live queue
    def plan_live_queue(self) -> None:
        for q in self.sc["live_queue"]:
            t = self.workday(self.end - timedelta(days=float(self.rng.uniform(0.6, 5))), 0)
            slots = [{"slot": s} for s in q.get("slots", [])]
            for d in slots:
                if d["slot"] == "E1":
                    d["variant"] = q.get("variant", "dotdot")
            author = None
            if q.get("author") == "trusted_newcomer":
                author = "newcomer"
            elif q.get("author_group") == "newcomer":
                author = self.contributor_for(t, first_time=True)
            area = q.get("area", "loader")
            pr: PRPlan | None
            if q["intent"] == "docs":
                pr = self.docs_pr(t, author)
                if q.get("slop"):
                    pr.kind = "slop_docs"
                    pr.slop_traits = list(q["slop"])
            elif q["intent"] == "build_ci":
                pr = self.build_pr(t, author, slots=[{"slot": "U1"}], change="fixtures_fetch")
            elif q["intent"] == "deps":
                pr = self.deps_pr(t, area, runtime=True, author=author,
                                  extra_slots=[d for d in slots if d["slot"] != "E3"])
            elif q["intent"] == "modify":
                pr = self.modify_pr(t, area, "refactor", author=author, slots=slots)
                if pr is None:
                    pr = self.feature_pr(t, area, author=author, slots=[d for d in slots if d["slot"] != "E7"])
            elif q["intent"] == "bugfix":
                pr = self.modify_pr(t, area, "bugfix", author=author, slots=slots) or \
                    self.feature_pr(t, area, author=author, slots=slots)
            else:
                pr = self.feature_pr(t, area, author=author, slots=slots,
                                     kind="slop" if q.get("slop") else "feature")
                if q.get("slop"):
                    pr.slop_traits = list(q["slop"])
            pr.live_key = q["key"]
            pr.expected_lane = q["expected_lane"]
            pr.expected_handoff = q.get("expected_handoff")
            pr.extra["tour"] = q.get("tour")
            pr.end = {"kind": "open"}
            pr.split = "live"
            self.add_pr(pr, review=False)

    def feature_requests(self) -> None:
        n = int(len([p for p in self.prs if p.split != "live"]) * 0.2)
        for _i in range(n):
            t = self.start + timedelta(days=float(self.rng.uniform(10, (self.end - self.start).days - 10)))
            kind = "question" if self.chance(0.3) else "feature"
            iss = IssuePlan(key=self.key("IS"), kind=kind, author=self.contributor_for(t), created_at=self.workday(t),
                            labels=["question"] if kind == "question" else ["enhancement"],
                            title_idx=int(self.rng.integers(0, 1000)))
            if self.chance(0.6):
                iss.closed_at = iss.created_at + timedelta(days=self.lognormal_days(10, 60))
                if iss.closed_at > self.end:
                    iss.closed_at = None
            self.issues.append(iss)

    # ------------------------------------------------------------------ main
    def run(self) -> dict[str, Any]:
        self.make_people()
        self.plan_history()
        self.prs.sort(key=lambda p: p.created_at)
        self.plan_anchor_events()
        self.plan_u1_events()
        self.realise_outcomes()
        # never reference modules that were reverted before the modify PR
        self.plan_live_queue()
        self.feature_requests()
        self.prs.sort(key=lambda p: p.created_at)
        self.number()
        for pr in self.prs:
            if pr.split != "live":
                pr.split = "holdout" if pr.created_at >= self.cutoff else "train"
        return self.to_json()

    def number(self) -> None:
        items: list[tuple[datetime, str, Any]] = [(p.created_at, "pr", p) for p in self.prs] + \
            [(i.created_at, "issue", i) for i in self.issues]
        items.sort(key=lambda x: (x[0], x[1]))
        for n, (_, _, obj) in enumerate(items, start=1):
            obj.number = n

    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1, "seed": self.w.seed, "profile": self.w.profile,
            "timeline": {"start": iso(self.start), "end": iso(self.end), "cutoff_v1": iso(self.cutoff),
                         "away": [[iso(a), iso(b)] for a, b in self.away]},
            "people": {k: dict(p.__dict__) for k, p in self.people.items()},
            "prs": [p.to_json() for p in self.prs],
            "issues": [i.to_json() for i in self.issues],
            "modules": {k: {kk: (iso(v) if isinstance(v, datetime) else v) for kk, v in m.items()}
                        for k, m in self.modules.items()},
            "anchors": {k: v for k, v in getattr(self, "anchor", {}).items()},
        }


def make_plan(w: World) -> dict[str, Any]:
    return Planner(w).run()

"""Routing into the four lanes (methodology 07 §1, §3). Pure functions: no I/O, property-testable.

The lens may raise attention, never lower it: a PR with a high or medium risk signal is never `shared`, and an
uncovered signal forces `unknown`, whatever the findings, overrides or assistant actions say.
"""

from __future__ import annotations

from typing import Any

from keeper.core.types import LANE_ORDER, Finding, Matching, RiskSignal, RoutedFinding
from keeper.route.risk import blocking, uncovered


def _rank(lane: str) -> int:
    return LANE_ORDER.index(lane) if lane in LANE_ORDER else len(LANE_ORDER)


def max_lane(lanes: list[str]) -> str:
    """The highest-priority lane, in the order unknown > edge > blind_spot > shared."""
    real = [x for x in lanes if x in LANE_ORDER]
    return min(real, key=_rank) if real else "shared"


def route_findings(lens: list[Finding], baseline: list[Finding], lb: Matching, blind_spot_matches: dict[str, str],
                   taxonomy: dict[str, Any]) -> list[RoutedFinding]:
    """Every lens and baseline finding lands in exactly one lane (FR-ROUTE-1…4)."""
    cats = taxonomy["categories"]
    out: list[RoutedFinding] = []
    matched_b: dict[str, str] = {}
    for p in lb.pairs:
        matched_b[p.b_id] = p.a_id
    for f in lens:
        pair = lb.partner_of_a(f.id)
        fixable = bool(cats.get(f.category, {}).get("fixable_default", False))
        if pair is not None:
            out.append(RoutedFinding(finding_id=f.id, paired_finding_id=pair.b_id, lane="shared",
                                     action="auto_fix" if fixable else "comment", fixable=fixable,
                                     evidence={"decision": pair.decision}))
        else:
            edge_fixable = fixable and f.category not in ("build_release", "dependency")
            out.append(RoutedFinding(finding_id=f.id, lane="edge", action="draft_and_offer_fix", fixable=edge_fixable))
    for b in baseline:
        if b.id in matched_b:
            continue  # represented by its lens partner in the shared lane
        item = blind_spot_matches.get(b.id)
        if item:
            out.append(RoutedFinding(finding_id=b.id, lane="blind_spot", action="surface_with_evidence",
                                     fixable=False, blind_spot_item_id=item))
        else:
            out.append(RoutedFinding(finding_id=b.id, lane="baseline_only", action="collapse", fixable=False))
    return out


def pr_lane(routed: list[RoutedFinding], signals: list[RiskSignal]) -> str:
    """FR-ROUTE-7 plus the absolute rule. baseline_only findings do not count."""
    lanes = [r.lane for r in routed if r.lane != "baseline_only"]
    if uncovered(signals):
        lanes.append("unknown")
    elif signals and blocking(signals):
        lanes.append("edge")  # a covered signal adds an edge note instead of forcing unknown
    lane = max_lane(lanes)
    if lane == "shared" and blocking(signals):
        lane = "edge"
    return lane


def override_allowed(current: str, new: str, signals: list[RiskSignal], *, owner: bool) -> tuple[bool, str | None]:
    """Overrides may raise attention freely; lowering is owner-only and never below the signals' floor."""
    if new == current:
        return True, None
    raising = _rank(new) < _rank(current)
    if raising:
        return True, None
    if not owner:
        return False, "only_owner_can_lower"
    if uncovered(signals) and new != "unknown":
        return False, "risk_signal"
    if new == "shared" and blocking(signals):
        return False, "risk_signal"
    return True, None


def apply_override(routed_lane: str, override: str | None, signals: list[RiskSignal]) -> str:
    """The lane after a stored override, re-checked against the absolute rule every time it is read."""
    if not override:
        return routed_lane
    ok, _ = override_allowed(routed_lane, override, signals, owner=True)
    return override if ok else routed_lane

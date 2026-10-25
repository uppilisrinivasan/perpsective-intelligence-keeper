"""Routing safety (NFR-SAFE-2): risk signals raise attention; the lens never lowers it."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from keeper.core.types import LANE_ORDER, RiskSignal, RoutedFinding
from keeper.route.lanes import apply_override, override_allowed, pr_lane

LANES = ["edge", "blind_spot", "shared", "baseline_only"]
signal = st.builds(RiskSignal, key=st.sampled_from(["build_script", "binary", "new_dependency"]), label=st.just("s"),
                   severity=st.sampled_from(["high", "medium", "low"]), covered=st.booleans())
routed = st.builds(RoutedFinding, finding_id=st.text(min_size=1, max_size=4), lane=st.sampled_from(LANES),
                   action=st.just("comment"))


@given(st.lists(routed, max_size=6), st.lists(signal, max_size=3),
       st.one_of(st.none(), st.sampled_from(list(LANE_ORDER))))
def test_risk_signal_never_shared(rs, sigs, override):
    lane = apply_override(pr_lane(rs, sigs), override, sigs)
    if any(s.severity in ("high", "medium") for s in sigs):
        assert lane != "shared"


@given(st.lists(routed, max_size=6), st.lists(signal, min_size=1, max_size=3))
def test_uncovered_signal_forces_unknown(rs, sigs):
    if any(not s.covered for s in sigs):
        assert pr_lane(rs, sigs) == "unknown"
        assert apply_override("unknown", "shared", sigs) == "unknown"
        assert override_allowed("unknown", "edge", sigs, owner=True)[0] is False


@given(st.lists(routed, max_size=6), st.lists(routed, max_size=6), st.lists(signal, max_size=3))
def test_lens_only_raises_attention(base, extra, sigs):
    """Adding lens findings to a PR's routed set never moves it to a lower-priority lane."""
    before = pr_lane(base, sigs)
    after = pr_lane(base + [r for r in extra if r.lane in ("edge", "shared")], sigs)
    assert LANE_ORDER.index(after) <= LANE_ORDER.index(before)

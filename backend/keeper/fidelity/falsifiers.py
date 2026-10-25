"""The papers' "what would prove us wrong", computed from the run as live checks (methodology 11 §5)."""

from __future__ import annotations

from typing import Any


def evaluate(metrics: dict[str, Any], cfg: dict[str, Any], growth: dict[str, Any] | None,
             practice: dict[str, Any] | None, names: dict[str, str]) -> list[dict[str, Any]]:
    fcfg = cfg
    m = metrics
    floor = float(fcfg["falsifier"]["noise_floor"])
    lens_rr = (m["lens"].get("residual_recall") or {}).get("value")
    lens_r = m["lens"]["substantive_recall"]["value"]
    base_r = m["baseline"]["substantive_recall"]["value"]
    car = (m["lens"].get("caricature_ratio") or {}).get("value")
    out = [
        {"key": "residual_noise", "result": f"residual recall {lens_rr:.0%}" if lens_rr is not None else "no residual",
         "passed": None if lens_rr is None else lens_rr > floor},
        {"key": "no_transfer", "result": f"lens {lens_r:.0%} vs generic {base_r:.0%}" if lens_r is not None and
         base_r is not None else "not enough data", "passed": None if lens_r is None or base_r is None else lens_r > base_r},
        {"key": "caricature", "result": f"max ratio {car:.2f}" if car is not None else "not enough data",
         "passed": None if car is None else car <= float(fcfg["caricature"]["max_ratio"])},
        {"key": "just_preference", "result": "not testable in v1", "passed": None},
    ]
    if growth and growth.get("trend"):
        t = growth["trend"]
        out.append({"key": "shrinks_people", "result": f"R+ per PR {t['r_plus_rate_prev']:.2f} → {t['r_plus_rate']:.2f}, "
                                                      f"hit rate {t['r_plus_hit_prev']:.0%} → {t['r_plus_hit']:.0%}",
                    "passed": not (t["r_plus_rate"] < t["r_plus_rate_prev"] * 0.9 and
                                   t["r_plus_hit"] >= t["r_plus_hit_prev"] * 0.9)})
        out.append({"key": "contrarians", "result": f"R+ {t['r_plus_rate_prev']:.2f} → {t['r_plus_rate']:.2f}, "
                                                   f"hit rate {t['r_plus_hit_prev']:.0%} → {t['r_plus_hit']:.0%}",
                    "passed": not (t["r_plus_rate"] > t["r_plus_rate_prev"] * 1.1 and
                                   t["r_plus_hit"] < t["r_plus_hit_prev"] * 0.9)})
    else:
        out.append({"key": "shrinks_people", "result": "not enough periods", "passed": None})
        out.append({"key": "contrarians", "result": "not enough periods", "passed": None})
    if practice and practice.get("before") is not None and practice.get("after") is not None:
        out.append({"key": "help_hollows", "result": f"unassisted recall {practice['before']:.0%} → {practice['after']:.0%}",
                    "passed": practice["after"] >= practice["before"]})
    else:
        out.append({"key": "help_hollows", "result": "no before/after practice data", "passed": None})
    out.append({"key": "loses_value", "result": "not testable in v1 (needs model generations)", "passed": None})
    return out

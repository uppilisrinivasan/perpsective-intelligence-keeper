"""Per-item calibration against outcomes (methodology 09 §3). Pure: counts in, posterior and status out."""

from __future__ import annotations

from typing import Any

from scipy.stats import beta as beta_dist


def posterior(k_bad: int, n_ignored: int, prior: dict[str, float]) -> dict[str, float]:
    a = float(prior["alpha"]) + k_bad
    b = float(prior["beta"]) + max(0, n_ignored - k_bad)
    return {"posterior_mean": a / (a + b), "ci90": [float(beta_dist.ppf(0.05, a, b)), float(beta_dist.ppf(0.95, a, b))],
            "alpha": a, "beta": b}


def lift(hit_rate: float, base_rate: float) -> float | None:
    return hit_rate / base_rate if base_rate > 0 else None


def edge_status(stats: dict[str, Any], cfg: dict[str, Any], *, bias_flagged: bool) -> str:
    """Build-time status (methodology 05 §3 step 9), then the outcome rule (09 §3)."""
    st = cfg["status"]
    if bias_flagged:
        return "bias_suspected"
    if stats.get("support", 0) < int(st["min_support"]) or \
            float(stats.get("trigger_precision") or 0) < float(st["min_trigger_precision"]):
        return "candidate"
    out = stats.get("outcome") or {}
    n_ign = int(out.get("ignored", 0))
    base = out.get("base_rate")
    if n_ign >= int(cfg["calibration"]["min_outcome_n"]) and base is not None and out.get("ci90") and \
            float(out["ci90"][1]) < float(base):
        return "candidate"
    return "validated"


def blind_spot_ok(stats: dict[str, Any], cfg: dict[str, Any]) -> bool:
    out = stats.get("outcome") or {}
    lf = out.get("lift")
    return int(out.get("bad_when_ignored", 0)) >= int(cfg["build"]["blind_spot_min_bad_outcomes"]) and \
        lf is not None and float(lf) >= float(cfg["calibration"]["blind_spot_min_lift"])


def confidence(item_status: str, posterior_mean: float | None, certainty: str, cfg: dict[str, Any]) -> str:
    """The categorical confidence of a lens finding (methodology 06 §3)."""
    hr = cfg["confidence"]["high_requires"]
    if item_status != "validated":
        return "low"
    if certainty == hr["model_certainty"] and posterior_mean is not None and posterior_mean >= float(hr["posterior_mean_min"]):
        return "high"
    if certainty in ("medium", "high"):
        return "medium"
    return "low"


def cost_weight(hit_rate: float, mean_severity_weight: float) -> float:
    return hit_rate * mean_severity_weight

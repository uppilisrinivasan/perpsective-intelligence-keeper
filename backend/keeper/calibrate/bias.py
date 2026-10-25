"""The group-tracking bias check (methodology 09 §5): does "P flagged item I" depend on the author's group, for
comparable changes? Mantel–Haenszel pooled odds ratio over strata (PR size × area), 95% CI by the
Robins–Breslow–Greenland variance. Pure."""

from __future__ import annotations

import math
from typing import Any


def mantel_haenszel(strata: list[tuple[int, int, int, int]]) -> dict[str, float | None]:
    """strata: (a, b, c, d) = (newcomer flagged, newcomer not, regular flagged, regular not)."""
    num = den = 0.0
    pr_sum = ps_qr = qs_sum = 0.0
    used = 0
    for a, b, c, d in strata:
        n = a + b + c + d
        if n == 0 or (a + b) == 0 or (c + d) == 0:
            continue
        used += 1
        r, s = a * d / n, b * c / n
        p, q = (a + d) / n, (b + c) / n
        num += r
        den += s
        pr_sum += p * r
        ps_qr += p * s + q * r
        qs_sum += q * s
    if used == 0 or num == 0 or den == 0:
        # zero cells: Haldane–Anscombe correction on the pooled table
        a = sum(x[0] for x in strata) + 0.5
        b = sum(x[1] for x in strata) + 0.5
        c = sum(x[2] for x in strata) + 0.5
        d = sum(x[3] for x in strata) + 0.5
        orr = a * d / (b * c)
        se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        return {"or": orr, "ci_low": math.exp(math.log(orr) - 1.96 * se), "ci_high": math.exp(math.log(orr) + 1.96 * se),
                "strata": used, "method": "pooled_corrected"}
    orr = num / den
    var = pr_sum / (2 * num ** 2) + ps_qr / (2 * num * den) + qs_sum / (2 * den ** 2)
    se = math.sqrt(var)
    return {"or": orr, "ci_low": math.exp(math.log(orr) - 1.96 * se), "ci_high": math.exp(math.log(orr) + 1.96 * se),
            "strata": used, "method": "mantel_haenszel"}


def size_bucket(changed_lines: int, buckets: list[int]) -> str:
    for b in buckets:
        if changed_lines <= b:
            return f"≤{b}"
    return f">{buckets[-1]}"


def check_item(rows: list[dict[str, Any]], cfg: dict[str, Any], outcome_rows: list[dict[str, Any]] | None = None
               ) -> dict[str, Any]:
    """rows: one per training PR where the item's triggers fire and P reviewed it:
    {group: newcomer|regular, flagged: bool, size: str, area: str}. outcome_rows: {group, bad: bool} for ignored."""
    b = cfg["bias"]
    strata: dict[tuple[str, str], list[int]] = {}
    n_by_group = {"newcomer": {"fires": 0, "flags": 0}, "regular": {"fires": 0, "flags": 0}}
    for r in rows:
        g = r["group"]
        if g not in n_by_group:
            continue
        n_by_group[g]["fires"] += 1
        n_by_group[g]["flags"] += int(r["flagged"])
        cell = strata.setdefault((r["size"], r["area"]), [0, 0, 0, 0])
        idx = (0 if r["flagged"] else 1) if g == "newcomer" else (2 if r["flagged"] else 3)
        cell[idx] += 1
    res = mantel_haenszel([tuple(v) for v in strata.values()])  # type: ignore[misc]
    enough = all(n_by_group[g]["fires"] >= int(b["min_per_group"]) for g in n_by_group)
    oc: dict[str, Any] = {"enough": False}
    if outcome_rows:
        by = {g: [r["bad"] for r in outcome_rows if r["group"] == g] for g in ("newcomer", "regular")}
        min_n = int(cfg["calibration"]["min_outcome_n"])
        if all(len(v) >= min_n for v in by.values()):
            rate = {g: sum(v) / len(v) for g, v in by.items()}
            oc = {"enough": True, "rates": rate, "n": {g: len(v) for g, v in by.items()},
                  "differs": rate["newcomer"] > rate["regular"] * float(b["or_threshold"]) / 2 + 1e-9 and
                  rate["newcomer"] - rate["regular"] > 0.1}
        else:
            oc = {"enough": False, "n": {g: len(v) for g, v in by.items()}}
    suspected = bool(enough and res["or"] is not None and res["or"] >= float(b["or_threshold"])
                     and (res["ci_low"] or 0) > 1 and not oc.get("differs", False))
    return {"odds_ratio": res["or"], "ci_low": res["ci_low"], "ci_high": res["ci_high"], "n_by_group": n_by_group,
            "outcome_check": oc, "verdict": "bias_suspected" if suspected else ("ok" if enough else "too_little_data"),
            "method": res["method"]}

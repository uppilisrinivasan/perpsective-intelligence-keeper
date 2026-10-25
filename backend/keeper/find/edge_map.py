"""Find: where the maintainer's eye matters most (methodology 10). Pure: per-cell counts in, ranked cells out."""

from __future__ import annotations

import math
from typing import Any


def area_for_path(path: str, depth: int) -> str:
    """Tests map to the area whose module stem they test (tests/test_include_x.py → <pkg>/include)."""
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    return "/".join(parts[:depth]) if len(parts) > depth else "/".join(parts[:-1])


def test_area(path: str, areas: list[str]) -> str:
    stem = path.rsplit("/", 1)[-1].removeprefix("test_").removesuffix(".py")
    for a in sorted(areas, key=len, reverse=True):
        last = a.rsplit("/", 1)[-1]
        if stem == last or stem.startswith(last + "_"):
            return a
    return "tests"


def compute(cells: dict[tuple[str, str], dict[str, Any]], area_prs: dict[str, int], area_volume: dict[str, float],
            tests_present: dict[str, bool], cfg: dict[str, Any], severity_weight: dict[str, float]
            ) -> list[dict[str, Any]]:
    """cells[(area, category)] = {r_plus, shared, bad: [{severity, days}], findings}; area_prs = reviewed PRs
    touching the area; area_volume = PRs per month over the last 12 months before the cutoff."""
    out = []
    sf = cfg["speed_factor"]
    for (area, cat), c in cells.items():
        n = max(1, area_prs.get(area, 0))
        rr = c["r_plus"] / n
        sr = c["shared"] / n
        cost = sum(severity_weight.get(b["severity"], 1.0) for b in c.get("bad", [])) / n
        days = sorted(b["days"] for b in c.get("bad", []) if b.get("days") is not None)
        speed = days[len(days) // 2] if days else None
        fast = tests_present.get(area, False) or (speed is not None and speed < float(sf["fast_days"]))
        vol = float(area_volume.get(area, 0.0))
        value = rr * (1 + float(cfg["cost_weight"]) * cost) * math.log1p(vol) * (float(sf["fast"]) if fast
                                                                                 else float(sf["default"]))
        mult = (rr + sr) / max(sr, 1e-9) if sr > 0 else None
        out.append({"area": area, "category": cat, "volume": vol, "residual_rate": rr, "shared_rate": sr,
                    "cost": cost, "speed_days": speed, "tests_present": bool(tests_present.get(area, False)),
                    "value": value, "findings": int(c.get("findings", 0)),
                    "multiplier": min(mult, float(cfg["multiplier_cap"])) if mult is not None else
                    float(cfg["multiplier_cap"]) if rr > 0 else None, "bad": c.get("bad", [])})
    return out


def rank(cells: list[dict[str, Any]], cfg: dict[str, Any], area_findings_by_anyone: dict[str, int] | None = None
         ) -> dict[str, list[dict[str, Any]]]:
    top = sorted([c for c in cells if c["findings"] >= int(cfg["min_findings"]) and c["value"] > 0],
                 key=lambda c: -c["value"])[: int(cfg["top_n"])]
    enough = sorted([c for c in cells if c["findings"] >= int(cfg["min_findings"]) and
                     c["shared_rate"] / max(1e-9, c["shared_rate"] + c["residual_rate"]) >= float(cfg["shared_dominant"])],
                    key=lambda c: -c["shared_rate"])[: int(cfg["enough_n"])]
    gaps = []
    if area_findings_by_anyone is not None:
        vols: dict[str, float] = {}
        for c in cells:
            vols[c["area"]] = max(vols.get(c["area"], 0.0), c["volume"])
        for a, v in sorted(vols.items(), key=lambda x: -x[1]):
            if v >= float(cfg.get("gap_volume_min", 1.0)) and area_findings_by_anyone.get(a, 0) < int(cfg["min_findings"]):
                gaps.append({"area": a, "category": "", "volume": v, "residual_rate": 0, "shared_rate": 0, "cost": 0,
                             "value": 0, "kind": "gap", "findings": area_findings_by_anyone.get(a, 0)})
        gaps = gaps[: int(cfg.get("gaps_n", 3))]
    return {"top": top, "enough": enough, "gaps": gaps}


def attention_bonus(cells_top: list[dict[str, Any]], pr_areas: list[str], cfg: dict[str, Any]) -> float:
    if not cells_top:
        return 0.0
    vmax = max(c["value"] for c in cells_top) or 1.0
    best = max((c["value"] for c in cells_top if c["area"] in pr_areas), default=0.0)
    return float(cfg["attention_bonus"]) * best / vmax

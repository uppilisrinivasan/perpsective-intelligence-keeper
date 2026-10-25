"""Print the eval table and write data/generated/eval_report.json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from keeper.config import get_settings


def write(report: dict[str, Any], *, simulated: bool) -> str:
    out = get_settings().data_dir / "generated" / "eval_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"created_at": datetime.now(UTC).isoformat(), "simulated": simulated, **report},
                              indent=2, default=str) + "\n")
    return str(out)


def table(report: dict[str, Any]) -> str:
    rows = [f"{'metric':34} {'value':>8} {'target':>8}  result"]
    for c in report["checks"]:
        v = "—" if c["value"] is None else f"{c['value']}"
        res = "not measured" if c["pass"] is None else ("pass" if c["pass"] else "FAIL")
        rows.append(f"{c['metric']:34} {v:>8} {c['target']!s:>8}  {res}")
    return "\n".join(rows)

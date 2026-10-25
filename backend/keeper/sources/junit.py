"""JUnit XML (pytest xunit2) parsing for the fix loop, via defusedxml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from defusedxml import ElementTree as ET


def parse(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"tests": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "time": 0.0, "failures": [],
                "missing": True}
    root = ET.parse(str(path)).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tests = failed = errors = skipped = 0
    t = 0.0
    failures: list[dict[str, str]] = []
    for s in suites:
        tests += int(s.attrib.get("tests", 0))
        failed += int(s.attrib.get("failures", 0))
        errors += int(s.attrib.get("errors", 0))
        skipped += int(s.attrib.get("skipped", 0))
        t += float(s.attrib.get("time", 0.0))
        for case in s.iter("testcase"):
            for tag in ("failure", "error"):
                el = case.find(tag)
                if el is not None:
                    name = f"{case.attrib.get('classname', '')}::{case.attrib.get('name', '')}".strip(":")
                    failures.append({"test": name, "message": (el.attrib.get("message") or "")[:500],
                                     "text": (el.text or "")[:6000]})
    return {"tests": tests, "passed": tests - failed - errors - skipped, "failed": failed + errors, "errors": errors,
            "skipped": skipped, "time": t, "failures": failures}

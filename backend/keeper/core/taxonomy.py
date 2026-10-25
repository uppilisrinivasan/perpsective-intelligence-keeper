"""Taxonomy helpers over the loaded `config/taxonomy.yaml` (passed in, so this stays pure)."""

from __future__ import annotations

from typing import Any


def categories(tax: dict[str, Any]) -> list[str]:
    return list(tax["categories"])


def substantive(tax: dict[str, Any], category: str, question_challenge: bool = False) -> bool:
    sub = tax["categories"].get(category, {}).get("substantive", True)
    if sub == "extractor_decides":
        return bool(question_challenge)
    return bool(sub)


def severity_rank(tax: dict[str, Any], severity: str) -> int:
    order = tax.get("severity_order", ["blocker", "major", "minor", "nit"])
    return order.index(severity) if severity in order else len(order)


def max_severity(tax: dict[str, Any], a: str, b: str) -> str:
    return a if severity_rank(tax, a) <= severity_rank(tax, b) else b

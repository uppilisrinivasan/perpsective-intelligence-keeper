"""Redaction of secret-shaped strings, e-mails and high-entropy tokens before anything reaches a model."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_TOKENISH = re.compile(r"[A-Za-z0-9+/=_\-]{32,}")


def shannon_bits(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


class Redactor:
    """Stable replacements per value within one call («SECRET_1»), so the model can still refer to them."""

    def __init__(self, cfg: dict[str, Any]):
        self.patterns = [(p["name"], re.compile(p["regex"]), p["replacement_kind"]) for p in cfg.get("patterns", [])]
        ent = cfg.get("entropy", {})
        self.min_len = int(ent.get("min_len", 32))
        self.min_bits = float(ent.get("min_bits", 4.0))
        self.allow = re.compile(cfg["allow_regex"]) if cfg.get("allow_regex") else None
        self.seen: dict[str, str] = {}
        self.counts: Counter[str] = Counter()
        self.hits: Counter[str] = Counter()

    def _token(self, kind: str, value: str) -> str:
        if value not in self.seen:
            self.counts[kind] += 1
            self.seen[value] = f"«{kind}_{self.counts[kind]}»"
        return self.seen[value]

    def __call__(self, text: str) -> str:
        if not text:
            return text
        for name, rx, kind in self.patterns:
            def sub(m: re.Match[str], kind: str = kind, name: str = name) -> str:
                self.hits[name] += 1
                return self._token(kind, m.group(0))
            text = rx.sub(sub, text)

        def ent(m: re.Match[str]) -> str:
            v = m.group(0)
            if len(v) < self.min_len or (self.allow and self.allow.match(v)) or v.startswith("«"):
                return v
            if shannon_bits(v) >= self.min_bits:
                self.hits["entropy"] += 1
                return self._token("SECRET", v)
            return v
        return _TOKENISH.sub(ent, text)

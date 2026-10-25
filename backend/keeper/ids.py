"""Opaque IDs with a type prefix: ULIDs (time-ordered, 26 Crockford base32 characters)."""

from __future__ import annotations

import hashlib
import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _b32(n: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_ALPHABET[n & 31])
        n >>= 5
    return "".join(reversed(out))


def ulid() -> str:
    ms = int(time.time() * 1000)
    rnd = int.from_bytes(os.urandom(10), "big")
    return _b32(ms, 10) + _b32(rnd, 16)


def new_id(prefix: str) -> str:
    return f"{prefix}_{ulid()}"


def stable_id(prefix: str, *parts: object) -> str:
    """A deterministic ID from content (used for snapshot rows and content-addressed records)."""
    h = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()
    return f"{prefix}_{h[:24]}"

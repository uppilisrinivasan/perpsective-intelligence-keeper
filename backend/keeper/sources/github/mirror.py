"""MirrorReader: one reader for the generated demo mirror and for imported mirrors (same layout as the REST API)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class MirrorReader:
    def __init__(self, root: Path):
        self.root = root
        meta = root / "_mirror.json"
        self.meta: dict[str, Any] = json.loads(meta.read_text()) if meta.exists() else {}

    def _pages(self, d: Path, stem: str) -> list[Any]:
        out: list[Any] = []
        for f in sorted(d.glob(f"{stem}.page-*.json")):
            out.extend(json.loads(f.read_text(encoding="utf-8")))
        return out

    def _one(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def repo(self) -> dict[str, Any]:
        return self._one(self.root / "repo.json") or {}

    def labels(self) -> list[dict[str, Any]]:
        return self._pages(self.root, "labels")

    def pull_numbers(self) -> list[int]:
        return [p["number"] for p in self._pages(self.root / "pulls", "index")]

    def pull(self, n: int) -> dict[str, Any] | None:
        return self._one(self.root / "pulls" / str(n) / "pull.json")

    def pull_files(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "pulls" / str(n), "files")

    def reviews(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "pulls" / str(n), "reviews")

    def review_comments(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "pulls" / str(n), "comments")

    def commits(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "pulls" / str(n), "commits")

    def issues(self) -> list[dict[str, Any]]:
        return self._pages(self.root / "issues", "index")

    def issue_comments(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "issues" / str(n), "comments")

    def timeline(self, n: int) -> list[dict[str, Any]]:
        return self._pages(self.root / "issues" / str(n), "timeline")

    def check_runs(self, sha: str) -> list[dict[str, Any]]:
        d = self._one(self.root / "commits" / sha / "check-runs.json")
        return d.get("check_runs", []) if d else []

    def iter_pulls(self) -> Iterator[dict[str, Any]]:
        for n in self.pull_numbers():
            p = self.pull(n)
            if p is not None:
                yield p

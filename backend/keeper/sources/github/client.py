"""The GitHub REST client. It exposes GET methods only (G1, NFR-SAFE-1): there is no code path that writes."""

from __future__ import annotations

import time
from typing import Any

import httpx

from keeper import __version__
from keeper.config import get_config, get_settings


class GitHubError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class GitHubClient:
    """Read-only. `get_*` methods only; the underlying httpx client is never given a write verb."""

    def __init__(self, on_wait: Any = None):
        s = get_settings()
        ing = get_config().ingest["import"]
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": ing["api_version"],
                   "User-Agent": ing["user_agent"].format(version=__version__)}
        token = s.GITHUB_TOKEN.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(base_url=s.GITHUB_API_URL.rstrip("/"), headers=headers, timeout=30)
        self.reserve = int(ing["rate_reserve"])
        self.on_wait = on_wait
        self.remaining: int | None = None

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, params: dict[str, Any] | None = None, etag: str | None = None) -> httpx.Response:
        headers = {"If-None-Match": etag} if etag else {}
        for _ in range(5):
            r = self._http.request("GET", path, params=params, headers=headers)
            rem = r.headers.get("x-ratelimit-remaining")
            self.remaining = int(rem) if rem and rem.isdigit() else self.remaining
            if r.status_code in (403, 429) and (r.headers.get("retry-after") or self.remaining == 0):
                wait = float(r.headers.get("retry-after") or max(1, int(r.headers.get("x-ratelimit-reset", "0"))
                                                                 - time.time()))
                if self.on_wait:
                    self.on_wait(wait)
                time.sleep(min(wait, 900))
                continue
            if self.remaining is not None and self.remaining < self.reserve:
                reset = int(r.headers.get("x-ratelimit-reset", "0"))
                wait = max(0, reset - time.time())
                if self.on_wait:
                    self.on_wait(wait)
                time.sleep(min(wait, 900))
            return r
        raise GitHubError("GitHub rate limit did not reset in time", 429)

    def get_json(self, path: str, params: dict[str, Any] | None = None, etag: str | None = None
                 ) -> tuple[Any, str | None, int]:
        r = self._get(path, params, etag)
        if r.status_code == 304:
            return None, etag, 304
        if r.status_code >= 400:
            raise GitHubError(f"GET {path}: HTTP {r.status_code}", r.status_code)
        return r.json(), r.headers.get("etag"), r.status_code

    def get_pages(self, path: str, params: dict[str, Any] | None = None, max_pages: int = 50,
                  stop: Any = None) -> list[list[Any]]:
        pages = []
        for page in range(1, max_pages + 1):
            data, _, _ = self.get_json(path, {**(params or {}), "per_page": 100, "page": page})
            if not data:
                break
            pages.append(data)
            if len(data) < 100 or (stop and stop(data)):
                break
        return pages

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return self.get_json(f"/repos/{owner}/{repo}")[0]

    def get_user(self, login: str) -> dict[str, Any]:
        return self.get_json(f"/users/{login}")[0]

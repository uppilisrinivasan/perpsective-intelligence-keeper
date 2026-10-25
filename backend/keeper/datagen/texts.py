"""Wording for PRs, reviews, replies, issues and commits, from the world's phrase banks (deterministic)."""

from __future__ import annotations

import hashlib
import string
from typing import Any


class _SafeDict(dict):  # type: ignore[type-arg]
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fill(template: str, **values: Any) -> str:
    return string.Formatter().vformat(template, (), _SafeDict({k: v for k, v in values.items() if v is not None}))


def choose(options: list[str], *key: object) -> str:
    h = int(hashlib.sha256("|".join(map(str, key)).encode()).hexdigest()[:8], 16)
    return options[h % len(options)]


def human(noun: str) -> str:
    return noun.replace("_", " ")


class Texts:
    def __init__(self, world: dict[str, Any]):
        self.w = world
        self.ph = world["phrases"]
        self.pt = world["pr_text"]

    def area_title(self, area: str) -> str:
        return str(self.w["areas"].get(area, {}).get("title", area))

    # ------------------------------------------------------------------ PRs
    def pr_title(self, pr: dict[str, Any], fn: str | None, key: str) -> str:
        kind, intent, area = pr["kind"], pr["intent"], pr["area"]
        vals = {"noun_h": human(pr.get("noun") or ""), "area_title": self.area_title(area),
                "area_title_cap": self.area_title(area).capitalize(), "fn": fn}
        if kind in ("slop", "slop_docs"):
            return fill(choose(self.pt["slop_titles"], key), **vals)
        if kind == "docs":
            topic = self.pt["docs_topics"][pr["extra"]["topic"] % len(self.pt["docs_topics"])]
            return fill(choose(self.pt["docs_titles"], key), topic=topic)
        if kind == "build":
            ch = pr["extra"].get("build")
            if ch in ("ci_python", "ci_cache"):
                return fill(choose(self.pt["build_titles"][:1], key), ci_change=choose(self.pt["ci_changes"], key))
            if ch in ("release_checksums", "release_fetch"):
                return fill(self.pt["build_titles"][1], rel_change=choose(self.pt["rel_changes"], key)
                            if ch == "release_checksums" else "bundle the sample configs")
            if ch == "fixtures_fetch":
                return "Regenerate test fixtures from upstream samples"
            return "Add compressed sample fixture for the loader tests"
        if kind == "deps":
            return fill(choose(self.pt["deps_titles"], key), dep=pr["extra"]["dep"], purpose=pr["extra"]["purpose"])
        if kind == "outcome_fix":
            return fill(choose(self.pt["bugfix_titles"], key), **vals)
        if kind == "modify":
            pool = {"bugfix": "bugfix_titles", "tests": "tests_titles"}.get(intent, "refactor_titles")
            return fill(choose(self.pt[pool], key), **vals)
        return fill(choose(self.pt["feature_titles"], key), **vals)

    def pr_body(self, pr: dict[str, Any], fn: str | None, test_file: str | None, key: str,
                issue_number: int | None = None, owner: str = "", repo: str = "") -> str:
        kind = pr["kind"]
        tl = fill(self.pt["test_line_with"], test_file=test_file) if test_file else self.pt["test_line_without"]
        vals = {"fn": fn, "noun_h": human(pr.get("noun") or ""), "area_title": self.area_title(pr["area"]),
                "test_line": tl, "issue": issue_number}
        if kind in ("slop", "slop_docs"):
            body = choose(self.pt["slop_body"], key)
            if "hallucinated_api" in pr.get("slop_traits", []):
                body += "\n\nThis also makes the new helper compatible with `lamina.compat.normalize_v2`."
            return body
        if kind == "docs":
            topic = self.pt["docs_topics"][pr["extra"]["topic"] % len(self.pt["docs_topics"])]
            return fill(choose(self.pt["docs_body"], key), topic=topic)
        if kind == "build":
            ch = pr["extra"].get("build")
            lines = {"ci_python": "Adds Python 3.13 to the test matrix.", "ci_cache": "Caches pip downloads in CI.",
                     "release_checksums": "The release script now prints the sha256 of each artefact.",
                     "release_fetch": "The release script now downloads the latest sample configs and bundles them.",
                     "binary_fixture": "Adds a gzip-compressed sample config for the loader tests.",
                     "fixtures_regen": "Regenerates the compressed fixtures.",
                     "fixtures_fetch": ("The fixture script now pulls the sample configs from the samples mirror and "
                                        "stores them compressed, and CI regenerates them before the tests. Also adds "
                                        "a new compressed fixture.")}
            return lines.get(ch, "Build changes.")
        if kind == "deps":
            return fill(self.pt["deps_body"][0], dep=pr["extra"]["dep"], purpose=pr["extra"]["purpose"], fn=fn)
        if kind == "outcome_fix" and issue_number:
            return fill(self.pt["bugfix_body"][1], **vals)
        if kind == "outcome_fix":
            return fill(self.pt["bugfix_body"][0], **vals)
        if kind == "modify":
            pool = {"bugfix": "bugfix_body", "tests": "tests_body"}.get(pr["intent"], "refactor_body")
            return fill(choose(self.pt[pool], key), **vals)
        return fill(choose(self.pt["feature_body"], key), **vals)

    def revert_title(self, title: str) -> str:
        return f'Revert "{title}"'

    def revert_body(self, owner: str, repo: str, n: int) -> str:
        return fill(self.pt["revert_body"], owner=owner, repo=repo, n=n)

    def commit_message(self, which: str, key: str, **vals: Any) -> str:
        return fill(choose(self.pt["commit_messages"][which], key), **vals)

    # ------------------------------------------------------------------ reviews
    def finding_comment(self, voice: str, slot: str, key: str, vals: dict[str, Any]) -> str:
        bank = self.ph.get(voice, {})
        options = bank.get(slot) or self.ph["maintainer"].get(slot) or ["Please take another look at this."]
        text = fill(choose(options, key, slot), **vals)
        if voice == "maintainer" and vals.get("suggestion") and choose(["y", "n", "n", "n", "n", "n"], key, "sg") == "y":
            text += f"\n\n```suggestion\n{vals['suggestion']}\n```"
        return text

    def social(self, voice: str, kind: str, key: str) -> str:
        bank = self.ph.get(voice, {})
        return choose(bank.get(kind) or self.ph["maintainer"][kind], key, kind)

    def review_body(self, voice: str, state: str, key: str) -> str:
        bank = self.ph.get(voice, {})
        if state == "CHANGES_REQUESTED":
            return choose(bank.get("review_body_changes") or self.ph["maintainer"]["review_body_changes"], key)
        return choose(bank.get("review_body_comment") or self.ph["maintainer"]["review_body_comment"], key)

    def reply(self, kind: str, key: str, **vals: Any) -> str:
        return fill(choose(self.ph["author_replies"][kind], key), **vals)

    def rejection(self, reason: str, key: str) -> str:
        return choose(self.ph["maintainer"]["rejection_dep" if reason == "dependency" else "rejection_slop"], key)

    # ------------------------------------------------------------------ issues
    def bug_issue(self, slot: str | None, vals: dict[str, Any]) -> tuple[str, str]:
        spec = self.w["issues"].get(slot or "base") or self.w["issues"]["base"]
        return fill(spec["title"], **vals), fill(spec["body"], **vals)

    def feature_issue(self, idx: int) -> tuple[str, str]:
        reqs = self.w["issues"]["feature_requests"]
        title = reqs[idx % len(reqs)]
        return title, f"{title}\n\nIt would make lamina easier to use in our setup."

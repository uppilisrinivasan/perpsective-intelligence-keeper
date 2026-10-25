"""GitHub REST payloads (API version 2022-11-28) built by code from the ledger, with GitHub's URL patterns, ID and
node_id conventions (docs/03-data/02-source-schema-github.md §3). Validated against the extracted OpenAPI schemas."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from keeper.datagen.execute import node_id

LICENSES = {"Apache-2.0": ("apache-2.0", "Apache License 2.0", "MDc6TGljZW5zZTI=")}


class GH:
    def __init__(self, api: str, html: str, owner: str, repo: str, people: dict[str, Any], owner_display: str,
                 description: str, license_id: str, repo_id: int, created_at: str, owner_id: int):
        self.api, self.html, self.owner, self.repo = api.rstrip("/"), html.rstrip("/"), owner, repo
        self.people = people
        self.owner_display = owner_display
        self.description = description
        self.license_id = license_id
        self.repo_id = repo_id
        self.created_at = created_at
        self.owner_id = owner_id
        self.pushed_at = created_at
        self.updated_at = created_at
        self.open_issues = 0
        self.size = 0
        self.r = f"{self.api}/repos/{owner}/{repo}"
        self.h = f"{self.html}/{owner}/{repo}"

    # ------------------------------------------------------------------ users
    def _user(self, login: str, uid: int, kind: str) -> dict[str, Any]:
        u = f"{self.api}/users/{login}" if kind != "Organization" else f"{self.api}/users/{login}"
        prefix = {"User": "U", "Bot": "BOT", "Organization": "O"}[kind]
        return {"login": login, "id": uid, "node_id": node_id(prefix, uid),
                "avatar_url": f"https://avatars.github.example/u/{uid}?v=4", "gravatar_id": "", "url": u,
                "html_url": f"{self.html}/{login}" if kind != "Bot" else f"{self.html}/apps/{login.replace('[bot]', '')}",
                "followers_url": f"{u}/followers", "following_url": f"{u}/following{{/other_user}}",
                "gists_url": f"{u}/gists{{/gist_id}}", "starred_url": f"{u}/starred{{/owner}}{{/repo}}",
                "subscriptions_url": f"{u}/subscriptions", "organizations_url": f"{u}/orgs", "repos_url": f"{u}/repos",
                "events_url": f"{u}/events{{/privacy}}", "received_events_url": f"{u}/received_events", "type": kind,
                "user_view_type": "public", "site_admin": False}

    def user(self, key: str) -> dict[str, Any]:
        p = self.people[key]
        return self._user(p["login"], p["gh_id"], "Bot" if p["role"] == "bot" else "User")

    def org(self) -> dict[str, Any]:
        return self._user(self.owner, self.owner_id, "Organization")

    # ------------------------------------------------------------------ repository
    def _repo_urls(self) -> dict[str, Any]:
        r = self.r
        return {
            "url": r, "html_url": self.h, "forks_url": f"{r}/forks", "keys_url": f"{r}/keys{{/key_id}}",
            "collaborators_url": f"{r}/collaborators{{/collaborator}}", "teams_url": f"{r}/teams",
            "hooks_url": f"{r}/hooks", "issue_events_url": f"{r}/issues/events{{/number}}", "events_url": f"{r}/events",
            "assignees_url": f"{r}/assignees{{/user}}", "branches_url": f"{r}/branches{{/branch}}",
            "tags_url": f"{r}/tags", "blobs_url": f"{r}/git/blobs{{/sha}}", "git_tags_url": f"{r}/git/tags{{/sha}}",
            "git_refs_url": f"{r}/git/refs{{/sha}}", "trees_url": f"{r}/git/trees{{/sha}}",
            "statuses_url": f"{r}/statuses/{{sha}}", "languages_url": f"{r}/languages",
            "stargazers_url": f"{r}/stargazers", "contributors_url": f"{r}/contributors",
            "subscribers_url": f"{r}/subscribers", "subscription_url": f"{r}/subscription",
            "commits_url": f"{r}/commits{{/sha}}", "git_commits_url": f"{r}/git/commits{{/sha}}",
            "comments_url": f"{r}/comments{{/number}}", "issue_comment_url": f"{r}/issues/comments{{/number}}",
            "contents_url": f"{r}/contents/{{+path}}", "compare_url": f"{r}/compare/{{base}}...{{head}}",
            "merges_url": f"{r}/merges", "archive_url": f"{r}/{{archive_format}}{{/ref}}",
            "downloads_url": f"{r}/downloads", "issues_url": f"{r}/issues{{/number}}", "pulls_url": f"{r}/pulls{{/number}}",
            "milestones_url": f"{r}/milestones{{/number}}", "notifications_url": f"{r}/notifications{{?since,all,participating}}",
            "labels_url": f"{r}/labels{{/name}}", "releases_url": f"{r}/releases{{/id}}",
            "deployments_url": f"{r}/deployments", "git_url": f"git://github.example/{self.owner}/{self.repo}.git",
            "ssh_url": f"git@github.example:{self.owner}/{self.repo}.git", "clone_url": f"{self.h}.git",
            "svn_url": self.h, "mirror_url": None,
        }

    def license(self) -> dict[str, Any] | None:
        if self.license_id not in LICENSES:
            return None
        key, name, nid = LICENSES[self.license_id]
        return {"key": key, "name": name, "spdx_id": self.license_id, "url": f"{self.api}/licenses/{key}", "node_id": nid}

    def repository(self) -> dict[str, Any]:
        return {"id": self.repo_id, "node_id": node_id("R", self.repo_id), "name": self.repo,
                "full_name": f"{self.owner}/{self.repo}", "private": False, "owner": self.org(),
                "description": self.description, "fork": False, **self._repo_urls(), "homepage": None,
                "language": "Python", "forks_count": 4, "forks": 4, "stargazers_count": 1240, "watchers_count": 1240,
                "watchers": 1240, "size": self.size, "default_branch": "main", "open_issues_count": self.open_issues,
                "open_issues": self.open_issues, "is_template": False, "topics": ["configuration", "config-files", "python"],
                "has_issues": True, "has_projects": False, "has_wiki": False, "has_pages": False,
                "has_downloads": True, "has_discussions": False, "archived": False, "disabled": False,
                "visibility": "public", "pushed_at": self.pushed_at, "created_at": self.created_at,
                "updated_at": self.updated_at, "allow_forking": True, "web_commit_signoff_required": False,
                "license": self.license()}

    def full_repository(self) -> dict[str, Any]:
        d = self.repository()
        d.update({"network_count": 4, "subscribers_count": 37, "organization": self.org(),
                  "security_and_analysis": None, "temp_clone_token": None})
        return d

    # ------------------------------------------------------------------ labels
    LABEL_COLORS = {"bug": "d73a4a", "enhancement": "a2eeef", "documentation": "0075ca", "question": "d876e3",
                    "dependencies": "0366d6", "ci": "ededed", "regression": "b60205"}

    def label(self, name: str, lid: int) -> dict[str, Any]:
        return {"id": lid, "node_id": node_id("LA", lid), "url": f"{self.r}/labels/{quote(name)}", "name": name,
                "color": self.LABEL_COLORS.get(name, "ededed"), "default": name in ("bug", "enhancement",
                                                                                     "documentation", "question"),
                "description": None, "archived_at": None, "archived_by": None}

    # ------------------------------------------------------------------ pulls
    def _links(self, n: int, head: str) -> dict[str, Any]:
        return {"self": {"href": f"{self.r}/pulls/{n}"}, "html": {"href": f"{self.h}/pull/{n}"},
                "issue": {"href": f"{self.r}/issues/{n}"}, "comments": {"href": f"{self.r}/issues/{n}/comments"},
                "review_comments": {"href": f"{self.r}/pulls/{n}/comments"},
                "review_comment": {"href": f"{self.r}/pulls/comments{{/number}}"},
                "commits": {"href": f"{self.r}/pulls/{n}/commits"}, "statuses": {"href": f"{self.r}/statuses/{head}"}}

    def pull_simple(self, rec: dict[str, Any], labels: list[dict[str, Any]], updated_at: str) -> dict[str, Any]:
        n, head = rec["number"], rec["head_sha"]
        author = self.user(rec["author"])
        repo = self.repository()
        reviewers = [self.user(k) for k in rec.get("pending_reviewers", [])]
        return {
            "url": f"{self.r}/pulls/{n}", "id": rec["gh_id"], "node_id": node_id("PR", rec["gh_id"]),
            "html_url": f"{self.h}/pull/{n}", "diff_url": f"{self.h}/pull/{n}.diff", "patch_url": f"{self.h}/pull/{n}.patch",
            "issue_url": f"{self.r}/issues/{n}", "commits_url": f"{self.r}/pulls/{n}/commits",
            "review_comments_url": f"{self.r}/pulls/{n}/comments", "review_comment_url": f"{self.r}/pulls/comments{{/number}}",
            "comments_url": f"{self.r}/issues/{n}/comments", "statuses_url": f"{self.r}/statuses/{head}",
            "number": n, "state": "open" if rec["state"] == "open" else "closed", "locked": False, "title": rec["title"],
            "user": author, "body": rec["body"], "labels": labels, "milestone": None, "active_lock_reason": None,
            "created_at": rec["created_at"], "updated_at": updated_at, "closed_at": rec.get("closed_at"),
            "merged_at": rec.get("merged_at"), "merge_commit_sha": rec.get("merge_commit_sha"), "assignee": None,
            "assignees": [], "requested_reviewers": reviewers, "requested_teams": [],
            "head": {"label": f"{self.people[rec['author']]['login']}:{rec['head_ref']}", "ref": rec["head_ref"], "sha": head,
                     "user": author, "repo": repo},
            "base": {"label": f"{self.owner}:main", "ref": "main", "sha": rec["base_sha"], "user": self.org(), "repo": repo},
            "_links": self._links(n, head), "author_association": rec["association"], "auto_merge": None,
            "draft": False,
        }

    def pull_full(self, rec: dict[str, Any], labels: list[dict[str, Any]], updated_at: str, files: list[dict[str, Any]],
                  n_comments: int, n_review_comments: int) -> dict[str, Any]:
        d = self.pull_simple(rec, labels, updated_at)
        merged = bool(rec.get("merged"))
        d.update({"merged": merged, "mergeable": None if rec["state"] != "open" else True, "rebaseable": None
                  if rec["state"] != "open" else True, "mergeable_state": "unknown" if rec["state"] != "open" else "clean",
                  "merged_by": self.user(rec["merged_by"]) if merged else None, "comments": n_comments,
                  "review_comments": n_review_comments, "maintainer_can_modify": rec["state"] == "open",
                  "commits": len(rec["commits"]), "additions": sum(f["additions"] for f in files),
                  "deletions": sum(f["deletions"] for f in files), "changed_files": len(files)})
        return d

    def diff_entry(self, f: dict[str, Any], head: str) -> dict[str, Any]:
        q = quote(f["filename"], safe="")
        d = {"sha": f["blob_sha"] or "0" * 40, "filename": f["filename"], "status": f["status"],
             "additions": f["additions"], "deletions": f["deletions"], "changes": f["changes"],
             "blob_url": f"{self.h}/blob/{head}/{q}", "raw_url": f"{self.h}/raw/{head}/{q}",
             "contents_url": f"{self.r}/contents/{q}?ref={head}"}
        if f.get("patch") is not None:
            d["patch"] = f["patch"]
        if f.get("previous_filename"):
            d["previous_filename"] = f["previous_filename"]
        return d

    def review(self, rv: dict[str, Any], n: int) -> dict[str, Any]:
        return {"id": rv["id"], "node_id": node_id("PRR", rv["id"]), "user": self.user(rv["reviewer"]),
                "body": rv["body"], "state": rv["state"], "html_url": f"{self.h}/pull/{n}#pullrequestreview-{rv['id']}",
                "pull_request_url": f"{self.r}/pulls/{n}",
                "_links": {"html": {"href": f"{self.h}/pull/{n}#pullrequestreview-{rv['id']}"},
                           "pull_request": {"href": f"{self.r}/pulls/{n}"}},
                "submitted_at": rv["submitted_at"], "commit_id": rv["commit_id"], "author_association": rv["association"]}

    def review_comment(self, c: dict[str, Any], n: int) -> dict[str, Any]:
        d = {"url": f"{self.r}/pulls/comments/{c['id']}", "pull_request_review_id": c["review_id"], "id": c["id"],
             "node_id": node_id("PRRC", c["id"]), "diff_hunk": c["diff_hunk"], "path": c["path"],
             "position": c["position"], "original_position": c["original_position"], "commit_id": c["commit_id"],
             "original_commit_id": c["original_commit_id"], "user": self.user(c["author"]), "body": c["body"],
             "created_at": c["created_at"], "updated_at": c["updated_at"],
             "html_url": f"{self.h}/pull/{n}#discussion_r{c['id']}", "pull_request_url": f"{self.r}/pulls/{n}",
             "author_association": c["association"],
             "_links": {"self": {"href": f"{self.r}/pulls/comments/{c['id']}"},
                        "html": {"href": f"{self.h}/pull/{n}#discussion_r{c['id']}"},
                        "pull_request": {"href": f"{self.r}/pulls/{n}"}},
             "start_line": c.get("start_line"), "original_start_line": c.get("start_line"),
             "start_side": None if c.get("start_line") is None else c["side"], "line": c["line"],
             "original_line": c["original_line"], "side": c["side"], "subject_type": c.get("subject_type", "line"),
             "reactions": self.reactions(f"{self.r}/pulls/comments/{c['id']}/reactions")}
        if c.get("in_reply_to"):
            d["in_reply_to_id"] = c["in_reply_to"]
        return d

    @staticmethod
    def reactions(url: str) -> dict[str, Any]:
        return {"url": url, "total_count": 0, "+1": 0, "-1": 0, "laugh": 0, "confused": 0, "heart": 0, "hooray": 0,
                "eyes": 0, "rocket": 0}

    def git_user(self, key: str, date: str) -> dict[str, Any]:
        p = self.people[key]
        return {"name": p["name"], "email": f"{p['gh_id']}+{p['login']}@users.noreply.github.example", "date": date}

    @staticmethod
    def verification() -> dict[str, Any]:
        return {"verified": False, "reason": "unsigned", "signature": None, "payload": None, "verified_at": None}

    def commit(self, c: dict[str, Any], tree: str) -> dict[str, Any]:
        sha = c["sha"]
        return {"sha": sha, "node_id": node_id("C", int(sha[:12], 16)),
                "commit": {"author": self.git_user(c["author"], c["authored_at"]),
                           "committer": self.git_user(c["committer"], c["committed_at"]), "message": c["message"],
                           "tree": {"sha": tree, "url": f"{self.r}/git/trees/{tree}"},
                           "url": f"{self.r}/git/commits/{sha}", "comment_count": 0, "verification": self.verification()},
                "url": f"{self.r}/commits/{sha}", "html_url": f"{self.h}/commit/{sha}",
                "comments_url": f"{self.r}/commits/{sha}/comments", "author": self.user(c["author"]),
                "committer": self.user(c["committer"]),
                "parents": [{"sha": p, "url": f"{self.r}/commits/{p}", "html_url": f"{self.h}/commit/{p}"}
                            for p in c["parents"]]}

    # ------------------------------------------------------------------ issues
    def issue(self, number: int, gh_id: int, title: str, body: str | None, author: str, labels: list[dict[str, Any]],
              state: str, created_at: str, updated_at: str, closed_at: str | None, comments: int,
              closed_by: str | None, state_reason: str | None, association: str,
              pull: dict[str, Any] | None = None) -> dict[str, Any]:
        d = {"id": gh_id, "node_id": node_id("I", gh_id), "url": f"{self.r}/issues/{number}",
             "repository_url": self.r, "labels_url": f"{self.r}/issues/{number}/labels{{/name}}",
             "comments_url": f"{self.r}/issues/{number}/comments", "events_url": f"{self.r}/issues/{number}/events",
             "html_url": f"{self.h}/{'pull' if pull else 'issues'}/{number}", "number": number, "state": state,
             "state_reason": state_reason, "title": title, "body": body, "user": self.user(author), "labels": labels,
             "assignee": None, "assignees": [], "milestone": None, "locked": False, "active_lock_reason": None,
             "comments": comments, "closed_at": closed_at, "created_at": created_at, "updated_at": updated_at,
             "closed_by": self.user(closed_by) if closed_by else None, "author_association": association,
             "reactions": self.reactions(f"{self.r}/issues/{number}/reactions"),
             "timeline_url": f"{self.r}/issues/{number}/timeline", "performed_via_github_app": None}
        if pull is not None:
            d["pull_request"] = pull
        return d

    def issue_comment(self, c: dict[str, Any], number: int, is_pull: bool) -> dict[str, Any]:
        return {"id": c["id"], "node_id": node_id("IC", c["id"]), "url": f"{self.r}/issues/comments/{c['id']}",
                "html_url": f"{self.h}/{'pull' if is_pull else 'issues'}/{number}#issuecomment-{c['id']}",
                "body": c["body"], "user": self.user(c["author"]), "created_at": c["created_at"],
                "updated_at": c["created_at"], "issue_url": f"{self.r}/issues/{number}",
                "author_association": c["association"], "performed_via_github_app": None,
                "reactions": self.reactions(f"{self.r}/issues/comments/{c['id']}/reactions")}

    # ------------------------------------------------------------------ timeline
    def _event_base(self, eid: int, event: str, actor: str, at: str, commit_id: str | None = None) -> dict[str, Any]:
        return {"id": eid, "node_id": node_id({"closed": "CE", "merged": "ME", "labeled": "LE",
                                                "review_requested": "RRE", "reopened": "REE"}.get(event, "E"), eid),
                "url": f"{self.r}/issues/events/{eid}", "actor": self.user(actor), "event": event,
                "commit_id": commit_id, "commit_url": f"{self.r}/commits/{commit_id}" if commit_id else None,
                "created_at": at, "performed_via_github_app": None}

    def ev_state(self, eid: int, event: str, actor: str, at: str, commit_id: str | None,
                 state_reason: str | None = None) -> dict[str, Any]:
        d = self._event_base(eid, event, actor, at, commit_id)
        if event == "closed":
            d["state_reason"] = state_reason
        return d

    def ev_labeled(self, eid: int, actor: str, at: str, name: str) -> dict[str, Any]:
        d = self._event_base(eid, "labeled", actor, at)
        d["label"] = {"name": name, "color": self.LABEL_COLORS.get(name, "ededed")}
        return d

    def ev_review_requested(self, eid: int, actor: str, at: str, requested: str) -> dict[str, Any]:
        d = self._event_base(eid, "review_requested", actor, at)
        d["review_requester"] = self.user(actor)
        d["requested_reviewer"] = self.user(requested)
        return d

    def ev_committed(self, c: dict[str, Any], tree: str) -> dict[str, Any]:
        sha = c["sha"]
        return {"sha": sha, "node_id": node_id("C", int(sha[:12], 16)), "url": f"{self.r}/git/commits/{sha}",
                "html_url": f"{self.h}/commit/{sha}", "author": self.git_user(c["author"], c["authored_at"]),
                "committer": self.git_user(c["committer"], c["committed_at"]), "tree": {"sha": tree,
                                                                                         "url": f"{self.r}/git/trees/{tree}"},
                "message": c["message"], "parents": [{"sha": p, "url": f"{self.r}/git/commits/{p}",
                                                      "html_url": f"{self.h}/commit/{p}"} for p in c["parents"]],
                "verification": self.verification(), "event": "committed"}

    def ev_reviewed(self, rv: dict[str, Any], n: int) -> dict[str, Any]:
        d = self.review(rv, n)
        d["event"] = "reviewed"
        return d

    def ev_cross_referenced(self, actor: str, at: str, source_issue: dict[str, Any]) -> dict[str, Any]:
        return {"actor": self.user(actor), "created_at": at, "updated_at": at,
                "source": {"type": "issue", "issue": source_issue}, "event": "cross-referenced"}

    def ev_commented(self, c: dict[str, Any], number: int, is_pull: bool) -> dict[str, Any]:
        d = self.issue_comment(c, number, is_pull)
        d["event"] = "commented"
        d["actor"] = self.user(c["author"])
        return d

    # ------------------------------------------------------------------ checks
    def check_run(self, cid: int, head_sha: str, name: str, conclusion: str, started: str, completed: str,
                  summary: str, pr_ref: dict[str, Any] | None) -> dict[str, Any]:
        app = {"id": 15368, "slug": "github-actions", "node_id": node_id("A", 15368), "owner": self.org(),
               "name": "GitHub Actions", "description": "Automate your workflow from idea to production",
               "external_url": "https://github.example/features/actions", "html_url": f"{self.html}/apps/github-actions",
               "created_at": "2018-07-30T09:30:17Z", "updated_at": "2019-12-10T19:04:12Z",
               "permissions": {"checks": "write", "contents": "read", "metadata": "read"},
               "events": ["check_run", "pull_request", "push"]}
        return {"id": cid, "head_sha": head_sha, "node_id": node_id("CR", cid), "external_id": f"{cid:x}",
                "url": f"{self.r}/check-runs/{cid}", "html_url": f"{self.h}/actions/runs/{cid // 3}/job/{cid}",
                "details_url": f"{self.h}/actions/runs/{cid // 3}/job/{cid}", "status": "completed",
                "conclusion": conclusion, "started_at": started, "completed_at": completed,
                "output": {"title": "Tests" if conclusion == "success" else "Tests failed", "summary": summary,
                           "text": None, "annotations_count": 0, "annotations_url": f"{self.r}/check-runs/{cid}/annotations"},
                "name": name, "check_suite": {"id": cid // 2}, "app": app, "pull_requests": [pr_ref] if pr_ref else []}

# Source schema: GitHub REST API

Keeper reads GitHub data from a **mirror**: a folder of JSON files that are byte-for-byte what the REST API returns (API version `2022-11-28`, media type `application/vnd.github+json`). The demo mirror is generated; an imported mirror is fetched. One reader (`keeper.sources.github.mirror.MirrorReader`) serves both.

## 1. Schema authority

The authoritative schemas are GitHub's OpenAPI description (`github/rest-api-description`, file `descriptions/api.github.com/api.github.com.json`). The build includes `scripts/extract_github_schemas.py`, which downloads a pinned commit of that file, extracts the component schemas below with their `$ref`s resolved, and writes them to `config/schemas/github/`. Both the data generator and the importer validate every file against them (JSON Schema draft 2020-12, `jsonschema` library).

| Mirror file | Endpoint | OpenAPI component (response) | Schema file |
|---|---|---|---|
| `repo.json` | `GET /repos/{owner}/{repo}` | `full-repository` | `full-repository.json` |
| `pulls/index.page-NNN.json` | `GET /repos/{o}/{r}/pulls?state=all&sort=created&direction=asc&per_page=100&page=N` | array of `pull-request-simple` | `pull-request-simple.json` |
| `pulls/<n>/pull.json` | `GET /repos/{o}/{r}/pulls/{n}` | `pull-request` | `pull-request.json` |
| `pulls/<n>/files.page-NNN.json` | `GET …/pulls/{n}/files?per_page=100` | array of `diff-entry` | `diff-entry.json` |
| `pulls/<n>/reviews.page-NNN.json` | `GET …/pulls/{n}/reviews?per_page=100` | array of `pull-request-review` | `pull-request-review.json` |
| `pulls/<n>/comments.page-NNN.json` | `GET …/pulls/{n}/comments?per_page=100` | array of `pull-request-review-comment` | `pull-request-review-comment.json` |
| `pulls/<n>/commits.page-NNN.json` | `GET …/pulls/{n}/commits?per_page=100` | array of `commit` | `commit.json` |
| `issues/index.page-NNN.json` | `GET /repos/{o}/{r}/issues?state=all&sort=created&direction=asc&per_page=100` | array of `issue` (PRs included, with a `pull_request` key, as GitHub does) | `issue.json` |
| `issues/<n>/comments.page-NNN.json` | `GET …/issues/{n}/comments?per_page=100` | array of `issue-comment` | `issue-comment.json` |
| `issues/<n>/timeline.page-NNN.json` | `GET …/issues/{n}/timeline?per_page=100` | array of `timeline-issue-events` (oneOf) | `timeline-issue-events.json` |
| `commits/<sha>/check-runs.json` | `GET /repos/{o}/{r}/commits/{ref}/check-runs` | `{total_count, check_runs: [check-run]}` | `check-run.json` |
| `labels.page-NNN.json` | `GET /repos/{o}/{r}/labels?per_page=100` | array of `label` | `label.json` |
| `_mirror.json` | (Keeper's own metadata, not an API response) | — | `config/schemas/mirror_meta.json` |

List endpoints are stored **as pages**, exactly as returned (`page-001` holds items 1–100). The reader concatenates them. `_mirror.json` records: `{api_version, api_base, html_base, generated_by: "keeper-datagen <version>" | "keeper-importer <version>", generated_at | fetched_at, owner, repo, endpoints: {<file>: {etag, fetched_at, pages}}}`.

## 2. Payloads, with the fields Keeper reads

Below, **bold** fields are read by Keeper. All other fields are present (as the schema requires) but unused. Abbreviated examples; real files contain every field.

### 2.1 Simple user (embedded everywhere)

```json
{"login": "mira-k", "id": 5100231, "node_id": "U_kgDOAE3Q5w", "avatar_url": "https://avatars.github.example/u/5100231?v=4",
 "gravatar_id": "", "url": "https://api.github.example/users/mira-k", "html_url": "https://github.example/mira-k",
 "followers_url": "https://api.github.example/users/mira-k/followers", "following_url": "https://api.github.example/users/mira-k/following{/other_user}",
 "gists_url": "https://api.github.example/users/mira-k/gists{/gist_id}", "starred_url": "https://api.github.example/users/mira-k/starred{/owner}{/repo}",
 "subscriptions_url": "https://api.github.example/users/mira-k/subscriptions", "organizations_url": "https://api.github.example/users/mira-k/orgs",
 "repos_url": "https://api.github.example/users/mira-k/repos", "events_url": "https://api.github.example/users/mira-k/events{/privacy}",
 "received_events_url": "https://api.github.example/users/mira-k/received_events", "type": "User", "user_view_type": "public", "site_admin": false}
```
Read: **login, id, type**. (The demo uses `github.example` hosts; see [Scenario](05-synthetic-world-scenario.md) §6.)

### 2.2 Pull request (`pull.json`)

Fields: `url, id, node_id, html_url, diff_url, patch_url, issue_url, commits_url, review_comments_url, review_comment_url, comments_url, statuses_url, number, state, locked, title, user, body, labels[], milestone, active_lock_reason, created_at, updated_at, closed_at, merged_at, merge_commit_sha, assignee, assignees[], requested_reviewers[], requested_teams[], head{label, ref, sha, user, repo}, base{label, ref, sha, user, repo}, _links{self, html, issue, comments, review_comments, review_comment, commits, statuses}, author_association, auto_merge, draft, merged, mergeable, rebaseable, mergeable_state, merged_by, comments, review_comments, maintainer_can_modify, commits, additions, deletions, changed_files`.

Read: **number, state, title, user, body, labels[].name, created_at, updated_at, closed_at, merged_at, merge_commit_sha, head.sha, head.ref, base.sha, base.ref, author_association, draft, merged, merged_by, additions, deletions, changed_files, requested_reviewers**.

`pull-request-simple` (the list endpoint) omits `merged, mergeable, rebaseable, mergeable_state, merged_by, comments, review_comments, maintainer_can_modify, commits, additions, deletions, changed_files`. The generator must omit them there too.

### 2.3 Diff entry (`files.page-NNN.json`)

```json
{"sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391", "filename": "strata/include.py", "status": "modified",
 "additions": 9, "deletions": 2, "changes": 11,
 "blob_url": "https://github.example/acme-oss/strata/blob/9f3c…/strata%2Finclude.py",
 "raw_url": "https://github.example/acme-oss/strata/raw/9f3c…/strata%2Finclude.py",
 "contents_url": "https://api.github.example/repos/acme-oss/strata/contents/strata%2Finclude.py?ref=9f3c…",
 "patch": "@@ -38,7 +38,14 @@ def resolve(base, name, root):\n …"}
```
`status` ∈ `added, removed, modified, renamed, copied, changed, unchanged`. `previous_filename` is present for renames. **`patch` is omitted for binary files and for very large diffs**, which is a real GitHub behaviour that the `binary_added_or_changed` signal relies on. The generator reproduces it: binary means no `patch`; a file diff over `github_sim.max_patch_bytes` (about 1 MB, never reached in the demo) has no `patch`.

Read: **filename, status, additions, deletions, patch, previous_filename, sha**.

### 2.4 Review (`reviews.page-NNN.json`)

```json
{"id": 2210331, "node_id": "PRR_kwDOAB…", "user": {…}, "body": "A few things before this can go in…",
 "state": "CHANGES_REQUESTED", "html_url": "https://github.example/acme-oss/strata/pull/212#pullrequestreview-2210331",
 "pull_request_url": "https://api.github.example/repos/acme-oss/strata/pulls/212",
 "_links": {"html": {"href": "…"}, "pull_request": {"href": "…"}},
 "submitted_at": "2024-05-02T09:14:55Z", "commit_id": "9f3c…", "author_association": "OWNER"}
```
`state` ∈ `APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING` (PENDING never appears in API output for other users). Read: **id, user, body, state, submitted_at, commit_id, author_association**.

### 2.5 Review comment (`comments.page-NNN.json`)

Fields: `url, pull_request_review_id, id, node_id, diff_hunk, path, position, original_position, commit_id, original_commit_id, in_reply_to_id (only on replies), user, body, created_at, updated_at, html_url, pull_request_url, author_association, _links{self, html, pull_request}, start_line, original_start_line, start_side, line, original_line, side, subject_type, reactions{url, total_count, +1, -1, laugh, hooray, confused, heart, rocket, eyes}`.

Read: **id, pull_request_review_id, in_reply_to_id, path, diff_hunk, line, start_line, side, start_side, original_line, subject_type, commit_id, user, body, created_at**.

How code computes the mechanical fields (for generation; the importer just stores them):

| Field | Computation |
|---|---|
| `diff_hunk` | From the file's patch at `commit_id`: the hunk header `@@ … @@` that contains the commented line, through the commented line inclusive (GitHub's convention) |
| `line`, `side` | The new-file line number and `RIGHT` for comments on added or context lines; the old-file line and `LEFT` for comments on removed lines |
| `start_line`, `start_side` | For multi-line comments; otherwise `null` |
| `position` | 1-based index of the commented line counted from the first line after the file's first `@@` header, continuing through later hunks (including their headers), per GitHub's definition |
| `original_*` | Equal to the current values when the comment's commit is the PR head when written. If later commits change the lines, `line` becomes `null` (outdated), and `original_line` and `original_commit_id` keep the old values. The generator applies the same rule when it later adds commits to the PR. |
| `pull_request_review_id` | The ID of the review the comment was submitted with (every inline comment belongs to a review, as on GitHub) |
| `subject_type` | `line`, or `file` for file-level comments |

### 2.6 Issue comment

`{id, node_id, url, html_url, body, user, created_at, updated_at, issue_url, author_association, performed_via_github_app: null, reactions{…}}`. Read: **id, user, body, created_at, author_association**.

### 2.7 Issue

`{id, node_id, url, repository_url, labels_url, comments_url, events_url, html_url, number, state, state_reason, title, body, user, labels[{id, node_id, url, name, color, default, description}], assignee, assignees, milestone, locked, active_lock_reason, comments, pull_request?{url, html_url, diff_url, patch_url, merged_at}, closed_at, created_at, updated_at, closed_by, author_association, reactions, timeline_url, performed_via_github_app}`.

Read: **number, state, state_reason, title, body, user, labels[].name, created_at, closed_at, pull_request (presence)**.

### 2.8 Timeline events

The timeline is a `oneOf` of event shapes, discriminated by `event`. Keeper reads these:

| `event` | Shape (key fields) | Keeper use |
|---|---|---|
| `closed` | `{id, node_id, url, actor, event, commit_id, commit_url, created_at, state_reason, performed_via_github_app}` | Rejection (actor), close time |
| `merged` | the same shape, with `commit_id` = merge commit | Merge actor |
| `reopened` | the same shape | Lifecycle |
| `cross-referenced` | `{actor, created_at, updated_at, source: {type: "issue", issue: {…issue}}, event}` | Links between bug issues and PRs |
| `referenced` | `{…, commit_id, commit_url}` | Commits mentioning the issue |
| `reviewed` | `{id, node_id, user, body, commit_id, submitted_at, state, html_url, pull_request_url, author_association, _links, event}` | Cross-check with reviews |
| `commented` | issue-comment fields plus `{event, actor}` | Cross-check |
| `committed` | `{sha, node_id, url, html_url, author{name, email, date}, committer{…}, tree{sha, url}, message, parents[], verification{…}, event}` | Commit order on the PR |
| `labeled` / `unlabeled` | `{…, label: {name, color}}` | Label history |
| `review_requested` | `{…, review_requester, requested_reviewer}` | Hand-off history |
| `head_ref_force_pushed` | `{…}` | Outdated comments |

### 2.9 Commit (PR commits)

`{sha, node_id, commit{author{name, email, date}, committer{name, email, date}, message, tree{sha, url}, url, comment_count, verification{verified, reason, signature, payload, verified_at}}, url, html_url, comments_url, author{simple user}|null, committer{simple user}|null, parents[{sha, url, html_url}]}`. Read: **sha, commit.message, commit.author.date, commit.committer.date, author.login, committer.login, parents**.

### 2.10 Check run

`{id, head_sha, node_id, external_id, url, html_url, details_url, status, conclusion, started_at, completed_at, output{title, summary, text, annotations_count, annotations_url}, name, check_suite{id}, app{…}, pull_requests[]}`. Read: **head_sha, name, status, conclusion, output.summary, completed_at**.

## 3. URL and ID conventions in generated data

| Value | Rule (code) |
|---|---|
| API base and HTML base | `scenario.github_sim.api_base` (default `https://api.github.example`) and `html_base` (default `https://github.example`). The importer keeps real `github.com` URLs. |
| `*_url` fields | Built from GitHub's documented URL patterns by `keeper.datagen.github_urls` (one function per resource; unit-tested against real payload samples shipped in `tests/fixtures/github_samples/`, which are real API responses from a public test repository, field names and patterns only) |
| `id` | Seeded, increasing integers per resource type, in realistic magnitudes (users about 10^6–10^8, PRs about 10^9, comments about 10^9) |
| `node_id` | A type prefix (`U_`, `R_`, `PR_`, `PRR_`, `PRRC_`, `IC_`, `I_`, `LA_`, `CR_`) plus `kgDO` plus seeded base64url |
| `number` | Shared sequence across issues and PRs, as on GitHub |
| SHAs | Real git SHAs from the generated repository |
| Timestamps | ISO 8601 UTC with `Z`, from the plan |
| `author_association` | From the persona and the time (a contributor's first PR is `FIRST_TIME_CONTRIBUTOR`; later ones `CONTRIBUTOR`; the maintainer is `OWNER`; the security reviewer is `MEMBER`) |
| `email` in commits | `<id>+<login>@users.noreply.github.example` |

## 4. The importer's behaviour for real repositories

See [External data](04-external-data.md) §1. It writes the same files, plus ETags in `_mirror.json`.

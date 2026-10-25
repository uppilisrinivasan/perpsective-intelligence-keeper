# External data: real repositories, CodeReviewer, OSV, Tavily

## 1. Importing a real repository (FR-IMP)

### 1.1 Choosing a repository for the README's real-data result

Criteria, from UC §3: a permissive licence (MIT, BSD or Apache-2.0); Python (so fixes can run); ≥ 3 years of PR history; one long-serving maintainer who wrote ≥ 300 substantive review comments; ≥ 150 reviewed PRs; tests runnable with `pytest` offline. Before naming the maintainer in the demo or video, **ask them** (UC §3, "ask maintainers before naming them"). Until they answer, the README reports aggregate metrics with the repository name only.

### 1.2 Procedure (`keeper.sources.github.importer`, job kind `import`)

1. **Validate input:** `owner/repo` matches `^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$`; the maintainer login exists (`GET /users/{login}`); the consent acknowledgement is present.
2. **Repository:** `GET /repos/{o}/{r}` → check the licence `spdx_id` is in `import.allowed_licenses`, else stop with an explanation.
3. **PR list:** `GET /pulls?state=all&sort=created&direction=desc&per_page=100`, paging until `created_at < since`. Pages are stored as returned.
4. **Per PR** (only PRs with ≥ 1 review or comment by a reviewer, plus all open PRs): `pull`, `files`, `reviews`, `comments`, `commits`, the issue `comments`, the issue `timeline`, and the check runs at the head SHA. About 8 requests per PR, so 300 PRs ≈ 2,400 requests, about half the hourly limit.
5. **Issues:** `GET /issues?state=all&since=<since>&labels=<bug_labels>` for outcome linking.
6. **Git:** `git clone --mirror`, then fetch `refs/pull/*/head`.
7. **Ingest** (the same code path as the demo), then run the learning pipeline as a follow-on job (with a cost estimate first).

### 1.3 HTTP behaviour

- Headers: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `Authorization: Bearer $GITHUB_TOKEN` (when set; unauthenticated works for small imports at 60 requests per hour), and `User-Agent: keeper-importer/<version>`.
- **Rate limits:** after each response, read `x-ratelimit-remaining` and `x-ratelimit-reset`. When remaining < `import.rate_reserve` (100), sleep until reset (the job shows "Waiting for GitHub rate limit (resets 14:32)"). On `403` or `429` with `retry-after`, honour it. Secondary limits: at most `import.max_concurrency` (4) concurrent requests.
- **Conditional requests:** store the `ETag` per file in `_mirror.json`; re-imports send `If-None-Match`; `304` keeps the file.
- **Resumable:** the job checkpoints per PR; a restart continues.
- **Storage:** `.runtime/mirror/github/<owner>/<repo>/` (git-ignored; never committed).

### 1.4 Attribution

Every displayed quotation from an imported project shows `@login` and links to `html_url`. Proof exports for imported projects contain IDs and metrics only, never bodies, unless the user ticks "Include quotations (I have permission)".

## 2. CodeReviewer dataset (optional, could)

The CodeReviewer dataset (Li et al., 2022; CC BY 4.0) pairs code changes with human review comments across many projects. Keeper can use its comment-generation split as a **second, generic** test of the matching judge and the baseline, but not for lenses: reviewers cannot be linked per person in a way that supports a lens.

- `scripts/fetch_codereviewer.py` downloads it from the URL in `config/datasets.yaml` into `.runtime/datasets/codereviewer/` (git-ignored).
- The adapter reads the JSONL records and maps the diff hunk field and the review message field to a situation with one human finding. Field names are validated at load against `config/datasets.yaml` `codereviewer.fields` [verify against the downloaded files], and the adapter fails clearly if they differ.
- Used by `./run.sh --eval --dataset codereviewer --limit 200`: it reports the baseline's recall of human comments and the judge's match decisions for spot checks.

## 3. OSV (always on for new dependencies)

- Endpoint: `POST https://api.osv.dev/v1/query` (`OSV_API_URL`), body `{"package": {"name": "<pkg>", "ecosystem": "PyPI"}, "version": "<version>"}`. The version is omitted for ranges; Keeper resolves the lowest version allowed by the specifier when it is pinned with `==`, and otherwise queries without a version and lists all advisories.
- Response: `{"vulns": [{"id", "summary", "details", "aliases", "modified", "published", "affected": […], "severity": [{"type", "score"}], "references": [{"type", "url"}]}]}`. It may be `{}` when there are none.
- Read: **id, summary, aliases, severity, references[].url**.
- Cached in `.runtime/cache/osv/` for `osv.cache_hours` (24). Timeout 10 s. On failure, the hand-off note says "Vulnerability check unavailable".

## 4. Tavily (optional; `TAVILY_API_KEY`)

- `POST https://api.tavily.com/search` with `Authorization: Bearer <key>`, body `{"query", "search_depth": "basic", "max_results": 5, "include_answer": false}`. Response: `{"query", "results": [{"title", "url", "content", "score"}], "response_time"}`.
- `POST https://api.tavily.com/extract` with `{"urls": [<pypi_url>, <repo_url>]}` for unfamiliar packages. Response: `{"results": [{"url", "raw_content"}], "failed_results": […]}`.
- Used only in hand-off notes (FR-ROUTE-10). Results are cited by URL. Cached for 24 hours.
- Disabled cleanly without a key ("Web check not configured" in the note; Settings shows the toggle as unavailable).

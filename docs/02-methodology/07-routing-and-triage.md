# Routing into four cases, and triage

> "The residual decides who teaches whom." (IP §6.2)

## 1. Finding-level routing (A6)

Inputs: lens findings L, baseline findings C, the L-vs-C matching, the lens version's blind-spot items, and risk signals.

| Situation | Lane | Rationale |
|---|---|---|
| A lens finding matched (match or partial) to a baseline finding | `shared` | Anyone would flag it: automate |
| A lens finding with no baseline match | `edge` | Only this person's eye flags it: learn from them, build through their lens |
| A baseline finding with no lens match, **and** it matches a `blind_spot` item (the `blind_spot_match` step below) | `blind_spot` | The person tends to miss this, and outcomes say it matters: teach |
| A baseline finding with no lens match and no blind-spot item | `baseline_only` (not a lane) | Probably noise for this project; shown collapsed under "Generic review also mentions (n)" |

**`blind_spot_match` (code first, then a check):** a baseline-only finding matches a blind-spot item if the item's triggers fire on the finding's file and hunk **and** the categories agree. Ambiguous cases (triggers fire, categories differ) are resolved with one `match_findings` call against the item's exemplars.

Each routed finding gets `action`:

| Lane | Default action | Fixable? |
|---|---|---|
| `shared` | `auto_fix` if the category's `fixable_default` is true, else `comment` | Yes, when allowed by the taxonomy |
| `edge` | `draft_and_offer_fix` | Yes, except for `build_release` and `dependency` (text only) |
| `blind_spot` | `surface_with_evidence` (show the outcome links: "2 bugs followed similar changes: #301, #355") | Offer only after the maintainer clicks "Good catch" |
| `baseline_only` | `collapse` | No |

## 2. Risk signals (code; `config/routing.yaml`)

Risk signals capture "unknown to both": changes where neither the generic reviewer nor this maintainer's history gives competence, and where history (xz) shows that attacks and accidents hide.

| Signal ID | Fires when | Default severity |
|---|---|---|
| `build_script_changed` | A changed path matches `build_paths` (`setup.py`, `setup.cfg`, `pyproject.toml` `[build-system]` or `[tool.*.scripts]` sections, `Makefile`, `*.m4`, `configure*`, `scripts/release*`, `scripts/build*`, `tox.ini`, `noxfile.py`) | high |
| `ci_workflow_changed` | `.github/workflows/**`, `.gitlab-ci.yml`, `.pre-commit-config.yaml` | high |
| `binary_added_or_changed` | A file with `status` added or modified and no `patch` (GitHub omits `patch` for binary files), or extension in `binary_exts` | high |
| `test_fixture_binary` | `binary_added_or_changed` under `tests/**` | high (the xz pattern) |
| `new_dependency` | Dependencies added in `pyproject.toml` (`[project] dependencies`, optional dependencies), `requirements*.txt` or `setup.cfg` | medium |
| `dependency_source_changed` | Index URLs, VCS URLs or hashes changed | high |
| `obfuscated_content` | An added line with a base64-like or hex-like run ≥ `entropy_min_len` (120) characters and Shannon entropy ≥ `entropy_min_bits` (4.5) | high |
| `permissions_or_policy_changed` | `CODEOWNERS`, `SECURITY.md`, `MAINTAINERS*`, `.github/settings.yml` | medium |
| `low_lens_coverage` | ≥ `coverage_min_lines` (30) changed lines in files where P has < `coverage_min_findings` (2) findings in history and no item's path triggers | low |
| `exec_or_network_in_code` | Added lines match `subprocess`, `os.system`, `eval(`, `exec(`, `pickle.loads`, `urllib.request`, `socket` in non-test code | medium |

**Coverage rule.** A fired signal is *covered* if a `validated` lens item (of P, or of another consenting lens in the project) has triggers that match the same files **and** the item's category is in the signal's `covering_categories`. A covered signal adds an `edge` note instead of forcing `unknown`.

**Absolute rule (NFR-SAFE-2).** If any signal with severity `high` or `medium` fires, the PR lane can never be `shared`, whatever the findings, overrides or assistant actions say. An uncovered signal forces `unknown`.

## 3. PR-level lane

`pr_lane = max(lanes of routed findings ∪ {unknown if any uncovered signal})`, with the order `unknown` > `edge` > `blind_spot` > `shared`. A PR with no routed findings and no signals is `shared`, with the note "Nothing for you here".

*Why `blind_spot` ranks below `edge`:* blind spots need a glance with the evidence; edge findings need the maintainer's judgment. `unknown` comes first because it needs a decision about *who* looks.

## 4. Triage (A7)

### 4.1 Triage signals (`triage_signals`, `fast` model)

Input: the PR context block **without** the author header fields (no login, no association). Output:

```json
{"summary": "Adds TOML-style dotted keys to the parser.",
 "slop": {"score": 0.82, "evidence": ["Description restates the diff generically", "Adds unused helper `_normalize2`", "Docstring references a nonexistent `strata.compat` module"]},
 "description_matches_diff": false,
 "touches_public_api": true}
```

Code combines `slop.score` with deterministic signals (`config/routing.yaml` `slop.*`): CI failed at the head; import errors in CI output; added lines referencing symbols that do not exist in the repository (checked with a symbol index built from the head checkout); the share of changed lines that are whitespace or comment-only. `slop_final = clamp(0.6·model + 0.4·rules)`. The PR gets the chip "Looks auto-generated" if `slop_final ≥ slop.threshold` (0.7).

**Bias guard:** the triage prompt and the slop rules never see login, association, account age or contribution counts. `test_slop_ignores_author_association` swaps associations on fixtures and requires identical scores.

Slop PRs whose routed findings are only `shared` or `baseline_only` get a drafted reply (the `slop_reply` template from `config/review.yaml`, filled in by the `review_draft` prompt). The reply asks politely for a clear description, a test, and confirmation the change was run locally. Keeper never closes the PR.

### 4.2 Attention estimate

```
attention_minutes(pr) = lane_base[pr_lane]
                      + per_finding[lane] × count(routed findings in lane, excluding baseline_only)
                      + per_100_changed_lines × changed_lines / 100 × lane_size_factor[pr_lane]
                      + edge_map_bonus(area)          # see Find, if enabled
                      − fixed_and_tested_discount × count(shared findings with a passing fix)
```

Defaults (`config/routing.yaml` `attention.*`): `lane_base` shared 1, blind_spot 3, edge 5, unknown 2 (deciding who looks and writing the hand-off); `per_finding` shared 0.5, blind_spot 2, edge 3; `per_100_changed_lines` 2; `lane_size_factor` shared 0.2, blind_spot 0.5, edge 1.0, unknown 0.3; `fixed_and_tested_discount` 0.5. Clamp to [1, 60] and round up to whole minutes.

The **naive baseline** for comparison (shown as "Reviewing everything yourself: ~3 h 10 min") is `naive_minutes = Σ (naive_base + naive_per_100 × changed_lines / 100)`, with `naive_base` 8 and `naive_per_100` 6.

These are estimates, labelled "≈" in the UI, with "How is this estimated?" linking to the formula. They are configuration, not claims.

### 4.3 Queue ordering

Lanes in order `unknown`, `edge`, `blind_spot`, `shared`. Within a lane: `attention_minutes` descending, then `created_at` ascending.

## 5. Hand-offs to another lens (A10)

### 5.1 Candidates

The pool is: people with a consenting lens in the project; CODEOWNERS owners of the changed paths; and reviewers with ≥ 3 substantive findings on the changed paths. The PR author and P are excluded.

Score for each candidate Q:

```
competence(Q) = Σ over fired uncovered signals s:  w_s × [Q has validated items covering s]  +  0.5 × [Q owns the paths in CODEOWNERS]
              + 0.3 × min(1, Q's substantive findings on these paths / 5)
distance(P, Q) = 1 − cosine(category_distribution(P), category_distribution(Q))      # on substantive findings
score(Q) = competence(Q) × (1 + λ × distance(P, Q))           # λ = handoff.distance_weight (0.5)
```

*Rationale (IP §5 L4):* "the most useful pair of lenses may be the two most distant credible ones". Competence comes first; distance breaks ties toward a different way of seeing. If no candidate has competence > 0, the UI says "No one in this project's history covers this. Consider asking a security reviewer.", and the risk signals are listed.

### 5.2 Hand-off note (`handoff_note`, `judge` model)

Input: the fired signals with evidence (paths, lines, entropy values), OSV results for new dependencies, Tavily results (optional), the PR summary, and Q's relevant lens items. Output: a short note ("Theo, could you look at #418? It changes `scripts/release.py` to download …; it also adds a binary fixture `tests/data/sample.bin` (12 KB). Neither Mira's history nor generic review covers release scripts. Things to check: …"). The note is labelled as Keeper's and copied by the user. Keeper does not send it.

### 5.3 Dependency checks (FR-ROUTE-10)

- **OSV:** for each new or changed dependency `{name, version}`, `POST {OSV_API_URL}/query` with `{"package": {"name", "ecosystem": "PyPI"}, "version"}`. Vulnerabilities are listed with IDs and summaries. No key needed. Results are cached for 24 hours.
- **Tavily (optional, `TAVILY_API_KEY`):** `POST https://api.tavily.com/search` with `query = "<package> PyPI package security advisory maintainer"`, `search_depth: "basic"`, `max_results: 5`, `include_answer: false`. When a package is not well known, Tavily `/extract` is used on its PyPI page and repository URL to read the maintainer, release history and repository link. The hand-off note cites the URLs. Results are cached for 24 hours. Without a key, the section says "Web check not configured".

## 6. Overrides

A maintainer can move a PR or a finding to another lane. Moves are stored as feedback (`feedback_events.kind = lane_override`). Moving *down* from `unknown` is blocked if an uncovered signal fired. The UI explains: "Keeper never lowers attention on build, release or binary changes. You can hand it to yourself instead." That button assigns P as the hand-off target, which keeps the lane.

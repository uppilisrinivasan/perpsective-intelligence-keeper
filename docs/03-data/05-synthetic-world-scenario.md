# Synthetic world scenario

The scenario (`config/datagen/scenario.yaml`) is the **specification of the demo world**. It fixes the *slots*: which people exist and in what roles, which concerns exist, how often, when, and with what consequences. The generator's models fill in the *values*: names, code, wording. Profiles (`config/datagen/profiles/full.yaml`, `small.yaml`) override counts.

## 1. Design goals

The world must contain, at realistic rates, every phenomenon Keeper detects, so that each feature is exercised and evaluable:

| Phenomenon | Exercises | Slot type |
|---|---|---|
| Concerns only the maintainer raises (invariants, history, threat model) | R+, the lens, the edge lane, Fidelity | `edge` |
| Concerns any good reviewer raises | The shared lane, the baseline's quality | `shared` |
| Concerns the maintainer misses that cause bugs | The blind-spot lane, calibration | `blind_spot` |
| A concern that tracks contributor group, not code | The bias check | `bias` |
| A concern that appears late | The growth residual, the lens diff | `drift` |
| Risky changes nobody covers | The unknown lane, hand-offs | `unknown` |
| A second reviewer with a different lens | Hand-off candidates, lens distance | the security reviewer's slots |
| Low-effort, AI-generated PRs | Slop triage | `slop` |
| Outcomes (reverts, bugs, follow-ups) | Calibration, Find | per-slot outcome model |

**Important:** the scenario cannot force the *baseline* (the real Nemotron) to miss anything. Edge slots are designed so that a generic reviewer *could not know* them from the diff alone (unwritten policy, history, invariants enforced only by the maintainer). Whether the baseline in fact misses them is **measured** after generation (validation V9). That measurement is reported, not assumed.

## 2. The scenario file (abridged, with every section shown)

```yaml
version: 1
seed: 20261025
profile: full                       # overridden by DATAGEN_PROFILE

github_sim:
  api_base: https://api.github.example
  html_base: https://github.example
  merge_style: merge                # merge | squash | rebase
  max_patch_bytes: 1000000

timeline:
  months: 36
  end: "2026-10-19T08:00:00Z"       # demo_now (a Monday 08:00 in the maintainer's timezone)
  holdout_months: 6
  maintainer_away:                  # periods when others merge without the maintainer's review
    - {start_month: 14, weeks: 3}
    - {start_month: 27, weeks: 3}

project:
  owner_kind: Organization
  domain_hint: "dependency-free Python library for layered configuration files with includes and environment interpolation"
  stack: {python: ">=3.9", test: "pytest==8.*", lint: "ruff"}
  size: {max_files: 24, max_lines_per_file: 320, target_tests: 150, max_suite_seconds: 15}
  areas:                            # names are templates; the world prompt proposes concrete module names that fit them
    - {id: lexer, role: "tokenizer, hot path"}
    - {id: parser, role: "parser to document model"}
    - {id: model, role: "document model, ordering, comments"}
    - {id: dump, role: "serializer; must round-trip"}
    - {id: include, role: "include directive resolution relative to a root"}
    - {id: interpolate, role: "environment variable interpolation"}
    - {id: loader, role: "public load/loads API, caching history"}
    - {id: errors, role: "error types with line and column"}
    - {id: cli, role: "command-line entry point"}
    - {id: build, role: "scripts/, CI workflow, packaging"}
    - {id: docs, role: "docs/ and README"}

people:
  maintainer: {count: 1, association: OWNER, timezone_pool: [Europe/Berlin, America/Toronto, Asia/Kolkata]}
  security_reviewer: {count: 1, association: MEMBER, reviews_share_in_areas: {include: 0.6, interpolate: 0.5, build: 0.8, parser: 0.3}}
  occasional_reviewers: {count: 2, association: CONTRIBUTOR, reviews_share: 0.08}
  contributors: {count: 34, association_mix: {FIRST_TIME_CONTRIBUTOR: 0.40, CONTRIBUTOR: 0.45, MEMBER: 0.10, NONE: 0.05}}
  trusted_newcomer: {count: 1, first_pr_month: 26, small_good_prs: 7}   # the build-script PR author in the live queue
  learner: {count: 1, role_hint: "contributor who wants to become a co-maintainer"}
  bots: [{login_hint: "ci-helper[bot]", type: Bot}]
  name_rules: {fictional: true, denylist_file: config/datagen/denylist.txt}

prs:
  history_total: 260
  merged_share: 0.78
  intents: {feature: 0.35, bugfix: 0.30, docs: 0.10, refactor: 0.10, tests: 0.05, build_ci: 0.05, deps: 0.05}
  size_lines: {distribution: lognormal, median: 38, p90: 220, max: 600}
  maintainer_review_share: 0.87
  review_latency_days: {distribution: lognormal, median: 2.0, p90: 9}
  rounds: {one: 0.55, two: 0.33, three_plus: 0.12}
  slop: {share_by_month: {"0-23": 0.0, "24-29": 0.06, "30-35": 0.18}, traits: [generic_description, unused_helper, hallucinated_api, unrelated_changes, failing_tests]}

concern_slots:                      # owner: maintainer | security_reviewer | any
  # --- maintainer's edge (generic reviewers cannot know these from the diff) ---
  - {id: E1, owner: maintainer, type: edge, category: security, areas: [include],
     hint: "resolved include paths must stay inside the root; symlinks count; an earlier fix missed symlinks",
     presence_rate: 0.45, flag_rate: 0.9, outcome_if_ignored: {post_merge_bug: 0.6}}
  - {id: E2, owner: maintainer, type: edge, category: invariant, areas: [dump, model],
     hint: "dump(load(x)) must preserve comments, key order and blank lines",
     presence_rate: 0.40, flag_rate: 0.85, outcome_if_ignored: {post_merge_bug: 0.4, reverted: 0.1}}
  - {id: E3, owner: maintainer, type: edge, category: dependency, areas: [build, any],
     hint: "no runtime dependencies, ever; optional extras only", presence_rate: 0.6, applies_to_intents: [deps, feature],
     flag_rate: 0.95, outcome_if_ignored: {reverted: 0.5}}
  - {id: E4, owner: maintainer, type: edge, category: performance, areas: [lexer],
     hint: "no per-character regex or allocation in the tokenizer loop", presence_rate: 0.35, flag_rate: 0.8,
     outcome_if_ignored: {follow_up_fix: 0.4}}
  - {id: E5, owner: maintainer, type: edge, category: history_context, areas: [loader],
     hint: "a load cache was added and removed earlier because of a race; reference that PR and issue",
     history_anchor: {pr_month: 9, issue_month: 10, revert_month: 10}, presence_rate: 0.5, flag_rate: 0.9,
     outcome_if_ignored: {post_merge_bug: 0.5}}
  - {id: E6, owner: maintainer, type: edge, category: invariant, areas: [errors, parser, include, interpolate],
     hint: "every user-facing error is a StrataError subclass carrying line and column", presence_rate: 0.3, flag_rate: 0.75,
     outcome_if_ignored: {follow_up_fix: 0.3}}
  - {id: E7, owner: maintainer, type: edge, category: api_compat, areas: [loader, model, dump],
     hint: "public parameters are deprecated with DeprecationWarning for one minor release before removal",
     presence_rate: 0.25, flag_rate: 0.9, outcome_if_ignored: {post_merge_bug: 0.5}}
  - {id: E8, owner: maintainer, type: edge, category: security, areas: [interpolate],
     hint: "never put environment values in error messages or logs", presence_rate: 0.3, flag_rate: 0.85,
     outcome_if_ignored: {post_merge_bug: 0.3}}
  # --- shared ground ---
  - {id: S1, owner: any, type: shared, category: tests, hint: "missing tests for new behaviour", presence_rate: 0.35, flag_rate: 0.7}
  - {id: S2, owner: any, type: shared, category: style, hint: "naming and formatting nits", presence_rate: 0.5, flag_rate: 0.5}
  - {id: S3, owner: any, type: shared, category: docs, hint: "missing changelog entry or docstring", presence_rate: 0.3, flag_rate: 0.6}
  - {id: S4, owner: any, type: shared, category: correctness, hint: "generic bug patterns: mutable default args, bare except, off-by-one",
     presence_rate: 0.15, flag_rate: 0.8, outcome_if_ignored: {post_merge_bug: 0.3}}
  # --- maintainer's blind spots (planted only; the maintainer rarely flags them) ---
  - {id: B1, owner: maintainer, type: blind_spot, category: correctness, areas: [loader, include, cli],
     hint: "open() without encoding='utf-8'; os.sep assumptions on Windows", presence_rate: 0.3, flag_rate: 0.1,
     outcome_if_ignored: {post_merge_bug: 0.55}}
  - {id: B2, owner: maintainer, type: blind_spot, category: correctness, areas: [loader, include],
     hint: "file handles not closed on error paths", presence_rate: 0.2, flag_rate: 0.15,
     outcome_if_ignored: {post_merge_bug: 0.45}}
  # --- bias ---
  - {id: X1, owner: maintainer, type: bias, category: tests, areas: [any],
     hint: "asks for a test for every branch", flag_rate_by_group: {newcomer: 0.6, regular: 0.18},
     presence: "always eligible on PRs with ≥ 2 new branches", outcome_if_ignored: {post_merge_bug: 0.03}}
  # --- drift ---
  - {id: D1, owner: maintainer, type: drift, category: design, areas: [loader, model, dump], starts_month: 30,
     hint: "type hints on public functions", presence_rate: 0.5, flag_rate: 0.8}
  # --- unknown to both ---
  - {id: U1, owner: none, type: unknown, category: build_release, areas: [build],
     hint: "release script change that downloads or embeds something", history_events: [{month: 20, merged: true, outcome: reverted}],
     flag_rate: 0.05}
  # --- security reviewer's lens ---
  - {id: T1, owner: security_reviewer, type: edge, category: build_release, areas: [build], hint: "build and release scripts must be reproducible and never fetch at build time", flag_rate: 0.9}
  - {id: T2, owner: security_reviewer, type: edge, category: security, areas: [build, any], hint: "binary test fixtures need a generator script and a checksum", flag_rate: 0.9}
  - {id: T3, owner: security_reviewer, type: edge, category: security, areas: [parser, include], hint: "recursion and include depth limits; quadratic inputs", flag_rate: 0.8}
  - {id: T4, owner: security_reviewer, type: edge, category: security, areas: [include], hint: "path confinement", flag_rate: 0.8}

outcomes:
  base_bad_rate: 0.03               # for merged PRs with no planted ignored issue
  bug_delay_days: {distribution: lognormal, median: 18, p90: 70}
  revert_delay_days: {median: 4, p90: 20}

live_queue:                          # open PRs at demo_now; expected lanes are ground truth only
  - {key: Q1, intent: feature, slop: [generic_description, unused_helper, failing_tests], expected_lane: shared}
  - {key: Q2, intent: docs, slop: [hallucinated_api], expected_lane: shared}
  - {key: Q3, intent: docs, slots: [], expected_lane: shared}
  - {key: Q4, intent: feature, author_group: newcomer, slots: [S1, S2, X1], expected_lane: shared}
  - {key: Q5, intent: bugfix, slots: [S4], expected_lane: shared}
  - {key: Q6, intent: feature, areas: [include], slots: [E1, S1], expected_lane: edge, tour: fix_demo}
  - {key: Q7, intent: refactor, areas: [dump], slots: [E2], expected_lane: edge}
  - {key: Q8, intent: refactor, areas: [loader], slots: [E7, D1], expected_lane: edge}
  - {key: Q9, intent: feature, areas: [cli], slots: [B1], expected_lane: blind_spot}
  - {key: Q10, intent: feature, areas: [loader], slots: [B2, S3], expected_lane: blind_spot}
  - {key: Q11, intent: build_ci, author: trusted_newcomer, changes: [scripts_build_fixtures, binary_fixture, ci_workflow], slots: [U1], expected_lane: unknown, expected_handoff: security_reviewer}
  - {key: Q12, intent: deps, areas: [lexer], slots: [E3, E4], signals: [new_dependency], expected_lane: edge}

learner_demo:
  sessions:
    - {kind: before, skill: {edge: 0.15, shared: 0.6, blind_spot: 0.3}}
    - {kind: learn,  skill: {edge: 0.35, shared: 0.65, blind_spot: 0.35}}
    - {kind: after,  skill: {edge: 0.55, shared: 0.7, blind_spot: 0.4}}
  own_eye_rate: 0.1                  # chance per item of a valid catch the maintainer did not make (from B-slots)
```

Rates are probabilities per eligible PR (an eligible PR touches one of the slot's areas). The plan stage (G3) samples them with the seed.

## 3. How slots become data

| Slot property | Code decides | AI writes |
|---|---|---|
| `presence_rate` | Whether a PR's change contains the issue (it becomes a constraint for `datagen_pr_change`: "this change must contain: <hint>, expressed naturally") | The code that contains the issue |
| `flag_rate` (by reviewer) | Whether the reviewer comments on it, and on which line (code picks the line from the applied diff where the issue is, via the change generator's `issue_locations` output, verified against the diff) | The comment's wording in the reviewer's voice |
| `outcome_if_ignored` | Whether a revert, bug issue or follow-up fix happens, and when | The issue text and the fix code |
| `history_anchor` | The earlier PR, issue and revert that later comments reference | Their content |
| `starts_month` (drift) | The flag rate is 0 before that month | — |
| `flag_rate_by_group` (bias) | Flag probability by author group | Wording |

The maintainer's comments that are **not** slot-driven (social remarks, questions, approvals) are planned by code (counts per PR from the persona's style parameters) and written by AI.

## 4. Personas

`datagen_world` proposes, within the constraints: the project name, organisation, module names, and for each person a display name, a login (lowercase, 3–12 characters plus an optional `-x` suffix), a timezone and a **voice card** (sentence length, directness, use of questions, emoji, code suggestion blocks, greeting habits). Voice cards drive `datagen_review` and `datagen_pr_text`. The maintainer's voice card also produces the style hints that Keeper later rediscovers, which is a small fidelity check of the style-hint extractor.

## 5. The repository's own evolution

- Month 0: the initial repository (G2): core lexer, parser, model, dump and errors, with tests.
- Months 1–35: PRs add features (includes in month 6, interpolation in month 12, the CLI in month 16, and so on, as `datagen_world` plans in a feature roadmap consistent with the areas), fix bugs, and refactor.
- The test count grows with merged PRs; the suite must stay under `max_suite_seconds`.

## 6. Safety of generated identities

- All hosts are `*.github.example` (RFC 2606 reserved), so no link resolves to a real account.
- Logins and names are checked against `config/datagen/denylist.txt` (well-known open-source maintainers and companies), and must not equal any login in `tests/fixtures/github_samples/`.
- The UI shows "Demo project (fictional)" next to the project name, and persona cards say "Fictional maintainer".
- No real CVE IDs. Security issues in the demo are described in prose, and OSV lookups only run on real package names that the live-queue PR adds (Q12 adds a real, well-known PyPI package chosen by `datagen_world` from an allow-list in `config/datagen/real_packages.yaml`).

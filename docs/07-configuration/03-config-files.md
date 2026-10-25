# Config files

Tunable, **non-secret** behaviour lives in `config/` (committed). Each file has a JSON Schema in `config/schemas/config/<name>.schema.json`; `keeper.config` validates all files at startup and `./run.sh --check` reports errors with the file and key. Values may reference environment variables as `${VAR:-default}`. **Code never repeats these defaults**: it reads them from the loaded config (the hardcode guard checks for numeric literals that duplicate config keys in `keeper/route`, `keeper/lens`, `keeper/fidelity` and `keeper/growth`).

| File | Purpose | Methodology reference |
|---|---|---|
| `models.yaml` | Roles, model IDs, fallback, reasoning parameters | [LLM gateway](../04-architecture/03-llm-gateway.md) §2 |
| `pricing.yaml` | USD per 1M tokens per model | Gateway §6 |
| `taxonomy.yaml` | Categories, severities, kinds, outcome compatibility | [Situations and findings](../02-methodology/01-situations-and-findings.md) §3 |
| `context.yaml` | PR context block bounds | Situations and findings §1 |
| `baseline.yaml` | The ruler's components | [Baseline](../02-methodology/03-baseline-the-ruler.md) §2 |
| `matching.yaml` | Candidate generation and weights | [Matching](../02-methodology/04-matching-and-residual.md) |
| `lens.yaml` | Building, statuses, calibration, bias, recall, feedback | Methodology 05, 06, 09, 13 |
| `routing.yaml` | Risk signals, slop, attention, hand-off, lanes | [Routing and triage](../02-methodology/07-routing-and-triage.md) |
| `review.yaml` | Review drafts, labels, slop reply template, exemplars | Methodology 06, 07, 14 |
| `fix.yaml` | Fix loop limits | [Fix loop](../02-methodology/08-fix-loop.md) |
| `sandbox.yaml` | Providers and recipes | [Sandbox runners](../04-architecture/05-sandbox-runners.md) |
| `find.yaml` | Edge map | [Find](../02-methodology/10-find-edge-map.md) |
| `fidelity.yaml` | Fidelity Test protocol and pass criteria | [Fidelity Test](../02-methodology/11-fidelity-test.md) |
| `growth.yaml` | Practice and health | [Growth Test](../02-methodology/12-growth-test-and-health.md) |
| `eval.yaml` | Targets for `./run.sh --eval` | [Ground truth](../03-data/07-ground-truth-and-validation.md) |
| `datasets.yaml` | External dataset URLs, licences | [External data](../03-data/04-external-data.md) |
| `redaction.yaml` | Secret and PII patterns | Gateway §8 |
| `glossary.yaml` | UI terms | [Copy guide](../06-frontend/06-copy-guide.md) §2 |
| `ui.yaml` | Editable settings, tour, suggestions, budgets | Frontend |
| `prompts/*.md`, `prompts/versions.lock` | Prompts | [Prompt catalog](../02-methodology/15-prompt-catalog.md) |
| `datagen/*` | Data generation scenario and profiles | [Synthetic data generation](../03-data/06-synthetic-data-generation.md) |
| `schemas/llm/*.json`, `schemas/github/*.json`, `schemas/lens_package.schema.json` | Output and source schemas | Methodology 15; Data 02 |

## Contents with defaults

### `pricing.yaml`
```yaml
currency: USD
per_million_tokens:
  nvidia/Nemotron-3_5-Lightning:       {input: 0.06, output: 0.24}
  nvidia/nemotron-3-super-120b-a12b:   {input: 0.30, output: 0.90}
  nvidia/Nemotron-3-Ultra-550b-a55b:   {input: 1.00, output: 3.00}
unknown_model_policy: most_expensive
batch_discount: null        # set if Token Factory publishes a batch price [verify]
reasoning_tokens_billed_as: output
```

### `taxonomy.yaml`
```yaml
severities: {blocker: {weight: 3}, major: {weight: 2}, minor: {weight: 1}, nit: {weight: 0.25}}
categories:
  correctness:     {substantive: true,  fixable_default: true,  label: "Correctness",        color: cat-correctness, description: "Logic errors, wrong results, edge cases, error handling"}
  api_compat:      {substantive: true,  fixable_default: true,  label: "API compatibility",  color: cat-api,         description: "…"}
  invariant:       {substantive: true,  fixable_default: true,  label: "Project rules",      color: cat-invariant,   description: "…"}
  security:        {substantive: true,  fixable_default: true,  label: "Security",           color: cat-security,    description: "…", never_shared_lane_on_fix: true}
  performance:     {substantive: true,  fixable_default: true,  label: "Performance",        color: cat-performance, description: "…"}
  history_context: {substantive: true,  fixable_default: true,  label: "Project history",    color: cat-history,     description: "…"}
  tests:           {substantive: true,  fixable_default: true,  label: "Tests",              color: cat-tests,       description: "…"}
  design:          {substantive: true,  fixable_default: true,  label: "Design",             color: cat-design,      description: "…"}
  docs:            {substantive: true,  fixable_default: true,  label: "Docs",               color: cat-docs,        description: "…"}
  build_release:   {substantive: true,  fixable_default: false, label: "Build and release",  color: cat-build,       description: "…"}
  dependency:      {substantive: true,  fixable_default: false, label: "Dependencies",       color: cat-dependency,  description: "…"}
  question:        {substantive: extractor_decides, fixable_default: false, label: "Question", color: cat-question,  description: "…"}
  style:           {substantive: false, fixable_default: true,  label: "Style",              color: cat-style,       description: "…"}
  social:          {substantive: false, fixable_default: false, label: "Social",             color: cat-social,      description: "…"}
kinds: [comment, change_request, rejection, question, maintainer_fix]
outcome_compat:
  post_merge_bug: [correctness, security, invariant, performance, api_compat]
  reverted: [correctness, security, invariant, performance, api_compat, build_release, dependency, design]
  follow_up_fix: [correctness, tests, docs, design, performance, invariant]
```
The descriptions ("…") are the full texts from [Situations and findings](../02-methodology/01-situations-and-findings.md) §3. Only `build_release` and `dependency` (and the non-substantive `question` and `social`) are text-only, as the methodology requires.

### `context.yaml`
```yaml
max_description_chars: 4000
max_diff_lines: 1500
max_repo_notes_chars: 2000
drop_first_when_over: [lock_files, generated_files]
anchor_snap_lines: 5
merge_duplicates: {line_window: 3, min_similarity: 0.8}
repo_notes_files: [CONTRIBUTING.md]
```
The author's login and history, and existing reviews or comments, are never in the context block (by code, not config).

### `baseline.yaml`
```yaml
llm: {role: judge, prompt: baseline_review, temperature: 0, top_p: 1, seed: 7, reasoning: low, max_findings: 15, allow_fallback: false}
tools:
  ruff:   {enabled: true, select: [E, F, B, UP, SIM, PERF], category_map: {F: correctness, B: correctness, PERF: performance, default: style}}
  bandit: {enabled: true, severity_min: low, category_map: {default: security}}
severity_map:
  ruff: {error: minor, warning: nit}
  bandit: {HIGH: major, MEDIUM: minor, LOW: nit}
```

### `matching.yaml`
```yaml
line_window: 6
min_lexical: 0.35
max_candidates_per_finding: 4
pre_score: {anchor: 0.5, lexical: 0.3, category: 0.2}
anchor_score: {overlap: 1.0, window: 0.6, same_file: 0.3}
weights: {match: 1.0, partial: 0.5}
judge_batch_size: 30
shallow_review_weight: 0.3
```

### `lens.yaml`
```yaml
build:
  min_sample_weight: 0.5
  cluster_distance: 0.55
  min_cluster_size: 3
  max_representatives: 8
  max_hunk_lines: 15
  trigger_min_coverage: 0.6
  max_exemplars: 6
  blind_spot_min_bad_outcomes: 2
  shared_min_findings: 5
  shared_min_overlap: 0.7
status:
  min_support: 4
  min_trigger_precision: 0.25
  retire_after_days: 540
calibration:
  prior: {alpha: 1, beta: 3}
  min_outcome_n: 3
  blind_spot_min_lift: 1.5
  severity_weights: {blocker: 3, major: 2, minor: 1, nit: 0.25}
  notes_ci_change: 0.1
bias:
  groups:
    newcomer: [FIRST_TIME_CONTRIBUTOR, FIRST_TIMER, NONE]
    regular: [CONTRIBUTOR, COLLABORATOR, MEMBER, OWNER]
  or_threshold: 2.0
  min_per_group: 5
recall:
  max_context_tokens: 400000
  max_items: 8
  max_findings: 12
  fallback: bm25
confidence:                       # categorical rules from methodology 06 §3
  high_requires: {status: validated, posterior_mean_min: 0.6, model_certainty: high}
feedback:
  accept_weight: 0.7
  edit_weight: 0.9
  add_note_weight: 1.0
  stable_id_jaccard: 0.5
  update_min_events: 5            # "Update lens" button appears at ≥ this many unconsumed events
schedule:
  recalibrate_cron: "0 6 * * 1"   # weekly; only used with JOB_RUNNER=nebius
```

### `routing.yaml`
```yaml
lane_order: [unknown, edge, blind_spot, shared]
signals:
  build_script_changed:   {severity: high,   build_paths: ["setup.py", "setup.cfg", "Makefile", "*.m4", "configure*", "scripts/release*", "scripts/build*", "tox.ini", "noxfile.py"], pyproject_sections: ["build-system", "tool.*.scripts"], covering_categories: [build_release]}
  ci_workflow_changed:    {severity: high,   paths: [".github/workflows/**", ".gitlab-ci.yml", ".pre-commit-config.yaml"], covering_categories: [build_release]}
  binary_added_or_changed: {severity: high,  binary_exts: [".bin", ".gz", ".xz", ".zip", ".so", ".dll", ".exe", ".whl", ".pyc"], covering_categories: []}
  test_fixture_binary:    {severity: high,   paths: ["tests/**"], covering_categories: []}
  new_dependency:         {severity: medium, covering_categories: [dependency, security]}
  dependency_source_changed: {severity: high, covering_categories: [dependency]}
  obfuscated_content:     {severity: high,   entropy_min_len: 120, entropy_min_bits: 4.5, covering_categories: []}
  permissions_or_policy_changed: {severity: medium, paths: ["CODEOWNERS", ".github/CODEOWNERS", "SECURITY.md", "MAINTAINERS*", ".github/settings.yml"], covering_categories: [security]}
  low_lens_coverage:      {severity: low,    coverage_min_lines: 30, coverage_min_findings: 2}
  exec_or_network_in_code: {severity: medium, patterns: ["subprocess", "os.system", "eval(", "exec(", "pickle.loads", "urllib.request", "socket"], covering_categories: [security]}
public_api_paths: ["src/*/__init__.py", "*/__init__.py"]
slop:
  model_weight: 0.6
  rules_weight: 0.4
  threshold: 0.7
  rules: {ci_failed: 0.3, import_errors: 0.3, nonexistent_symbols: 0.3, whitespace_comment_share: 0.1}
attention:
  lane_base: {shared: 1, blind_spot: 3, edge: 5, unknown: 2}
  per_finding: {shared: 0.5, blind_spot: 2, edge: 3}
  per_100_changed_lines: 2
  lane_size_factor: {shared: 0.2, blind_spot: 0.5, edge: 1.0, unknown: 0.3}
  fixed_and_tested_discount: 0.5
  clamp: [1, 60]
  naive_base: 8
  naive_per_100: 6
handoff:
  distance_weight: 0.5
  codeowners_weight: 0.5
  path_findings_weight: 0.3
  path_findings_cap: 5
  min_path_findings: 3
  signal_weights: {high: 1.0, medium: 0.6, low: 0.3}
osv:    {cache_hours: 24, timeout_seconds: 10, ecosystem: PyPI}
tavily: {cache_hours: 24, search_depth: basic, max_results: 5}
shared_in_top_cell_note: true
```

Category names in `covering_categories` must exist in `taxonomy.yaml` (validated at startup). Whether a finding is fixable comes from `taxonomy.yaml` `fixable_default`.

### `review.yaml`
```yaml
label_line: "— Drafted by Keeper from {maintainer}'s review patterns. Edited and sent by a human."
max_exemplars: 16
exemplar_hunk_lines: 12
draft_event_rules: {blocker_or_major: REQUEST_CHANGES, otherwise: COMMENT}
slop_reply_template: |
  Thanks for the contribution! To help us review it, could you:
  - describe what problem this solves and how you tested it,
  - add or update a test that covers the change,
  - confirm the test suite passes locally?
```

### `fix.yaml`
```yaml
max_iterations: 4
branches: 2
run_timeout_seconds: 900
max_changed_lines: 200
repair: {max_failure_chars: 6000}
targeted_tests_first: true
```

### `find.yaml`
```yaml
area_depth: 2
min_findings: 5
top_n: 6
enough_n: 4
shared_dominant: 0.7
cost_weight: 1.0
speed_factor: {fast: 1.2, default: 1.0, fast_days: 14}
multiplier_cap: 10
attention_bonus: 3
```

### `fidelity.yaml`
```yaml
holdout: {months: 6, min_findings: 1}
leakage: {allow_rolling_exemplars: false}
bootstrap: {n: 2000, seed: 13, ci: 0.95}
caricature: {top_k: 3, max_ratio: 1.3}
pass: {max_noise_ratio: 1.0, require_unknown_recall_demo: 1.0}
falsifier: {noise_floor: 0.1}
sensitivity: {line_windows: [3, 10], partial_as: [0, 1]}
batch: {min_requests: 20, poll_seconds: 20}
```

### `growth.yaml`
```yaml
practice:
  min_findings: 2
  max_changed_lines: 250
  k: 5
  strata: {easy: 1, medium: 2, hard: 2}
  costly_threshold: 0.5
  balance: {max_mean_difficulty_diff: 0.25, max_profile_l1: 0.3}
growth:
  period_months: 3
  deadband: 0.1
  min_prs_per_period: 8
  g_floor: 0.05
```

### `eval.yaml`
```yaml
extraction: {precision_min: 0.9, recall_min: 0.85}
matching: {kappa_min: 0.7}
baseline: {shared_slot_recall_min: 0.7, blind_spot_slot_recall_min: 0.6}
routing: {macro_f1_min: 0.8, unknown_recall: 1.0}
edge_map: {planted_in_top4_min: 3}
```

### `ui.yaml`
```yaml
editable_settings:
  attention_budget_minutes: {type: int, default: 120, min: 15, max: 600}
  auto_approve_usd: {type: float, default: "${KEEPER_AUTO_APPROVE_USD:-0.05}", min: 0, max: 1.0}
  theme: {type: enum, options: [system, light, dark], default: system}
  density: {type: enum, options: [comfortable, compact], default: comfortable}
  diff_wrap: {type: bool, default: false}
  diff_view: {type: enum, options: [unified, split], default: unified}
  reduced_motion: {type: enum, options: [system, on], default: system}
  show_baseline_only: {type: bool, default: false}
tour:
  steps: [aha_compare, fix_demo, queue_summary, unknown_row, edge_map, proof_verdict, practice_taste]
  aha_max_diff_lines: 120
assistant:
  max_tool_rounds: 6
  history_tokens: 24000
  tool_result_tokens: 6000
  suggestions:
    queue: ["Why does #{top_unknown} need another reviewer?", "What's handled for me this week?"]
    pr: ["What would {maintainer} notice here?", "Show me past comments like “{top_edge_title}”."]
    lens: ["What changed in my lens since v{prev_version}?", "What does my lens miss?"]
    proof: ["Explain the result in one paragraph."]
    practice: ["What should I practise next?"]
jobs: {poll_status_seconds: 60}
```

### `redaction.yaml`, `glossary.yaml`, `datasets.yaml`
- `redaction.yaml`: a list of `{name, regex, replacement_kind}` plus `entropy: {min_len: 32, min_bits: 4.0}`.
- `glossary.yaml`: `terms: [{key, label, short, long_md}]`, covering every term marked as a `Term` in the UI (lanes, lens, baseline, residual, edge map, Fidelity Test, Growth Test, health states, ruler, falsifier).
- `datasets.yaml`: `codereviewer: {url, licence, citation}` and similar entries, with no credentials.

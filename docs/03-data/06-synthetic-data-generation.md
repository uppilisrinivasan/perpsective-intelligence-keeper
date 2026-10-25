# Synthetic data generation

The demo needs a realistic, internally consistent history of one open-source project: three years of PRs, reviews, comments, issues, CI and outcomes, plus the git repository itself. This document defines how `keeper.datagen` produces it, so that:

1. every file has **exactly the schema the real source produces** (validated against GitHub's OpenAPI schemas, real git, and real pytest JUnit XML);
2. **AI generates only values.** Structure, identifiers, timing, counts, URLs, diffs, hunks, line numbers, SHAs and test results come from code or from actually running git and pytest;
3. the data contains every planted phenomenon of the [scenario](05-synthetic-world-scenario.md), with **ground truth kept separately**;
4. generation is **reproducible, resumable and auditable**, and its outputs are **committed to git**.

Entry points: `python -m keeper.datagen run` and `./run.sh --generate-data`. Generation is a build-team task. Users and judges never need to run it, because the outputs are in the repository.

## 1. Who produces which value (the contract)

Code review checks every generator change against this table.

| Value | Produced by | How |
|---|---|---|
| Which PRs, issues and events exist; their order, dates, authors, reviewers, intents, rounds, merge or close, outcomes | **Code** (G3 plan, seeded) | Sampling from the scenario's distributions |
| Which concern slots are present in each PR, and whether each reviewer flags them | **Code** | `presence_rate`, `flag_rate`, group and drift rules |
| Field names, nesting, optional fields, page splits, `*_url` values, `id`, `node_id`, `number` | **Code** | GitHub schema plus URL and ID conventions ([GitHub schema](02-source-schema-github.md) §3) |
| `author_association`, `state`, `merged`, `draft`, labels, `requested_reviewers` | **Code** | From the plan |
| Project name, module names, feature roadmap, persona names, logins, voice cards, slot wording | **AI** (`datagen_world`) | Within the scenario's constraints; checked against the denylist |
| Initial source code and tests | **AI** (`datagen_repo_code`), validated by **pytest** | A repair loop until green and under the time budget |
| Each PR's code change, including planted issues, and the author's fix-up commits | **AI** (`datagen_pr_change`), validated by **pytest** and **slot validators** | Search-and-replace edits applied by code |
| Diffs, `patch`, `additions`, `deletions`, `changes`, file `status`, `sha`, `previous_filename` | **Real git** | `git diff --numstat`, `git diff -M` at the planned commits |
| `diff_hunk`, `line`, `side`, `position`, `original_*`, outdated comments | **Code** from real diffs | The rules in [GitHub schema](02-source-schema-github.md) §2.5 |
| Which line a reviewer comments on | **Code** | From the change generator's `issue_locations`, verified against the diff |
| PR titles and bodies | **AI** (`datagen_pr_text`) | In the author's voice; slop PRs use the slop traits |
| Review comment, review body and conversation comment texts | **AI** (`datagen_review`, `datagen_thread_reply`) | For planned findings only; the model gets the slot hint and the anchored hunk |
| Commit messages | **AI** (`datagen_commit_message`) | — |
| Commit SHAs, merge commits, reverts, tree states | **Real git** | `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` from the plan; `git revert -m 1` |
| JUnit XML and check-run conclusions | **Real pytest** | Run at every PR head; only `timestamp` and `hostname` are rewritten |
| Issue titles and bodies (bug reports, features) | **AI** (`datagen_issue`) | For planned outcome events: "a user reports <symptom of slot E1>" |
| Issue numbers, labels, cross-references, closing PRs | **Code** | From the plan |
| Binary test fixtures | **Code** | For example `gzip` of a generated sample config |
| Ground-truth labels | **Code** | From the plan and slot validators; written only to `data/ground_truth/` |
| Demo learner notes | **AI** (`datagen_learner_notes`) for findings **code** selected by skill level | — |

## 2. Stages

Each stage reads the previous stages' outputs from the **generation ledger** (`.runtime/datagen/ledger.sqlite` plus `.runtime/datagen/work/`) and is content-addressed: its cache key is the hash of (scenario section, inputs, prompt versions, model IDs, seed). Re-running skips unchanged stages; `--from <stage>` forces a stage and everything after it.

| # | Stage | Kind | Output |
|---|---|---|---|
| G0 | Load the scenario and profile, validate against `config/schemas/datagen/scenario.schema.json`, resolve | code | `work/plan/scenario.resolved.json` |
| G1 | World: names, modules, roadmap, voice cards, slot wording | AI | `work/world/world.json` |
| G2 | Initial repository: code and tests; pytest repair loop; initial commits (including CODEOWNERS, MAINTAINERS, CONTRIBUTING, SECURITY, CI, scripts) | AI + pytest + git | `work/repo/` (a git working copy) |
| G3 | Plan: the full timeline of PRs, commits, review rounds, findings to plant, issues, reverts, outcome-induced fix PRs, CI, the live queue | code | `work/plan/plan.json`, `work/plan/truth.partial.json` |
| G4 | Execute the timeline in order: changes, commits, texts, reviews, replies, fix-ups, merges or closes, reverts, issues, CI | AI + git + pytest + code | ledger rows; the repository's history |
| G5 | The live queue: open PRs at `demo_now` (changes, texts, CI; no maintainer reviews) | as G4 | ledger rows |
| G6 | Demo learner sessions | code + AI | `work/learner/*.json` |
| G7 | Emit the GitHub mirror from the ledger | code | `data/sources/github/<owner>/<repo>/**` |
| G8 | Emit git and CI artefacts | git + code | `data/sources/git/<repo>.bundle`, `data/sources/ci/junit/*.xml` |
| G9 | Validate (§6) | code (V9b optionally live) | `data/generated/validation_report.json` (generation fails on any error) |
| G10 | Write the ground truth | code | `data/ground_truth/**` |
| G11 | Manifest and hashes | code | `data/manifest.json` |
| G12 | Snapshot: run Keeper's own pipeline on the generated data, then evaluate | Keeper pipeline (needs a key) | `data/snapshots/<project>/**`, `data/generated/eval_report.json` |

## 3. G2: an initial repository that really runs

1. `datagen_repo_code` receives the world (modules, roles, conventions) and returns `{files: [{path, content}]}` within the size limits. The maintainer's invariants (E2 round-trip, E6 error positions, E3 no runtime dependencies) are **already true** in the initial code, so later violations are real deviations.
2. Code writes the files, creates a virtual environment in `.runtime/datagen/venv` (pytest and ruff versions from `scenario.stack`), runs `pytest -q`, and on failure sends the failing output back (`max_repair_attempts`, 3). The suite must finish within `max_suite_seconds`.
3. Code adds the policy files from templates, with AI-written prose sections, and makes back-dated initial commits as the maintainer.

## 4. G3: the plan (code only)

The plan is one JSON document. Excerpt for one PR:

```json
{
  "key": "PR-0212", "number": 212, "author": "per_kai", "intent": "feature", "area": ["include"],
  "created_at": "2024-04-29T13:02:11Z", "base": "main@2024-04-29T13:02:11Z",
  "slots_present": [{"slot": "E1", "variant": "symlink_escape"}, {"slot": "S1"}],
  "rounds": [
    {"reviewer": "per_mira", "at": "2024-05-02T09:14:55Z", "state": "CHANGES_REQUESTED",
     "findings": [{"slot": "E1", "severity": "major"}, {"slot": "S1", "severity": "minor"}],
     "social": 1, "body": true},
    {"author_fixup": {"addresses": ["E1", "S1"], "at": "2024-05-03T18:40:00Z"}},
    {"reviewer": "per_mira", "at": "2024-05-04T08:01:00Z", "state": "APPROVED", "findings": [], "social": 1, "body": false}
  ],
  "end": {"kind": "merged", "at": "2024-05-04T08:03:12Z", "by": "per_mira"},
  "ci": "per_head",
  "outcomes": []
}
```

Plan rules:
- Area and intent follow the roadmap. Slot presence is sampled per eligible area. At most 3 planted slots per PR, to keep changes small.
- Whether the maintainer reviews: `maintainer_review_share`, and never during `maintainer_away` (then another reviewer or nobody reviews; a PR merged in those weeks with a present edge or blind-spot slot is a candidate for an outcome).
- Flags: a Bernoulli trial with the reviewer's `flag_rate` for each present slot (group-dependent for X1; 0 before `starts_month` for D1). The security reviewer reviews by area share and flags their own T-slots.
- **Addressed or ignored:** a flagged slot is addressed in a fix-up with probability `scenario.prs.address_rate` (0.85). Unflagged present slots stay in the merged code.
- **Outcomes:** for each merged PR with ignored or unflagged present slots, sample each slot's `outcome_if_ignored`. Outcomes become future events: a bug issue at `merge + bug_delay`, closed by a planned bugfix PR (which modifies the same lines, so blame linking works); a revert at `merge + revert_delay` (a GitHub-style revert PR); a follow-up fix PR. Base-rate outcomes (`base_bad_rate`) are added to clean PRs, so that outcomes are not perfectly predictive.
- History anchors (E5): the cache PR in month 9, the race bug issue in month 10, and the revert in month 10 are planned explicitly. Later maintainer comments on loader-cache changes reference them (`refs.history`), and code puts the real numbers into the comment request ("mention #<n>").
- Slop PRs: by month share; traits drive the change (unused helper, nonexistent API) and the text; most are closed unmerged with a polite maintainer comment.
- Live queue: as listed in the scenario, all created in the 5 days before `demo_now`, with authors chosen by the scenario's rules.

## 5. G4: executing one PR

```
for event in plan.timeline (ordered by time):
  PR opened:
    1. worktree at the planned base (main at that time)
    2. datagen_pr_change(world, area files' current content, intent, slots_present with variants and hints, size target, voice)
       → {edits[], new_files[], issue_locations: [{slot, path, line_hint, snippet}]}
    3. apply edits (exact search-and-replace; failures go back to the model, ≤ 3 attempts)
    4. run pytest → must pass, except when the plan says this head fails CI (slop failing_tests, or planted test failures)
    5. slot validators (§6 V5) → each planted slot must be detectable at its issue_location; repair otherwise
    6. commit(s) by the author at the planned times (messages from datagen_commit_message)
    7. datagen_pr_text → title, body
  Review round:
    8. for each planned finding: code picks the anchor (issue_location → nearest changed line in the diff),
       builds diff_hunk and line fields from the real patch at the current head
    9. datagen_review(reviewer voice, findings with slot hints, anchored hunks, history refs with real numbers, social count, state)
       → {review_body?, comments: [{finding_ref, body}], conversation?: [...]}
   10. author replies (datagen_thread_reply) per the plan
  Author fix-up:
   11. datagen_pr_change(mode = address, findings to address) → edits → apply → pytest → commit
   12. recompute outdated comments (line = null where hunks changed)
  End:
   13. merge (git merge --no-ff with the planned date; conflicts → regenerate the PR change against the new base, ≤ 2 times, else re-plan as closed) or close
   14. timeline events, CI per head (pytest at each head → JUnit → check runs)
  Revert: git revert -m 1 <merge sha> on a branch → revert PR (texts from templates: GitHub's own revert wording, which is code, not AI)
  Issue: datagen_issue for the planned symptom → issue; cross-references and closing PR by code
```

**Parallelism.** PRs whose base is the same main commit and whose areas are disjoint are generated concurrently (`DATAGEN_CONCURRENCY`, default 3). Merges are always applied in timeline order.

## 6. Validation (G9); generation fails on any error

| ID | Check |
|---|---|
| V1 | Every mirror file validates against its GitHub OpenAPI schema (§1 of the GitHub schema document). |
| V2 | Referential integrity: every `user.id` is known; `pull_request_review_id` exists; `in_reply_to_id` is in the same PR; `head.sha` and `merge_commit_sha` exist in the bundle; issue cross-references point to real numbers. |
| V3 | Diff fidelity: for every PR, recomputing `git diff base...head` reproduces `files[].patch`, `additions` and `deletions` exactly; every non-outdated comment's `diff_hunk` is a prefix-consistent excerpt of its file's patch, and `line` is inside it. |
| V4 | Test reality: pytest at the final `main` passes; recorded check-run conclusions equal a re-run at a sample of 20 heads (`--deep` re-runs all). |
| V5 | Slot validators: each planted slot is detectable in code at its location by a deterministic check per slot type (for example: B1 → an AST call to `open` without `encoding=`; B2 → an `open` outside `with` on a path with a `raise`; E3 → a `pyproject` dependency added; E4 → `re.` call inside the tokenizer loop body; E7 → a public parameter removed from a signature without `warnings.warn(..., DeprecationWarning)`; E2 → a round-trip property test fails on the planted sample, run by code; E1 → a traversal test fails on the planted resolver; others → the `slot_check` regex or AST rule in `config/datagen/slot_checks.yaml`). |
| V6 | Timeline consistency: created ≤ reviews ≤ merged; commits ordered; no activity by the maintainer during away periods; business-hour distributions per timezone. |
| V7 | Rates: observed slot presence, flag and outcome rates are within ±50% (relative) of the planned rates (catches generator bias). |
| V8 | Size: `data/` ≤ the budget in [Data folder](08-data-folder-and-git.md); the suite is ≤ `max_suite_seconds`. |
| V9 | Ground-truth completeness: every human finding's source comment maps to a planted finding or a planned social or question comment. |
| V9b | Optional, live (`--measure-baseline`): run the baseline (the real ruler) on the history PRs and report, per slot, the share caught by the baseline. Edge slots with baseline catch > 0.5 are reported as **"not an edge in practice"**. The report is committed; the slot is not hidden. |

## 7. Determinism and resumption

- All sampling uses `numpy.random.Generator(PCG64(seed + stage_offset))`.
- Model outputs are cached by request hash in the ledger, so re-running with the same models replays them exactly. Changing a prompt version invalidates only the dependent calls.
- `python -m keeper.datagen run --resume` continues after a crash from the last completed event.

## 8. Cost and models

| Prompt | Role | Calls (full) | Approx. cost |
|---|---|---|---|
| `datagen_world` | deep | 2–3 | $0.05 |
| `datagen_repo_code` | deep | 2–5 | $0.30 |
| `datagen_pr_change` (including fix-ups and repairs) | deep (configurable to judge) | ~520 | $7–9 |
| `datagen_pr_text`, `datagen_review`, `datagen_issue`, `datagen_slop_pr` | judge | ~900 | $1.50 |
| `datagen_thread_reply`, `datagen_commit_message` | fast | ~1,400 | $0.20 |
| G12 snapshot (Keeper's pipeline on all reviewed and live PRs) | mixed | — | $2–4 |
| **Total** | | | **≈ $11–15** (capped by `DATAGEN_SPEND_CAP_USD`) |

The `small` profile costs about $3 and is used for development. The committed data uses the `full` profile.

## 9. Commands

```bash
python -m keeper.datagen run --profile full                  # G0–G11
python -m keeper.datagen run --profile full --from G4        # force re-execution from G4
python -m keeper.datagen validate [--deep] [--measure-baseline]
python -m keeper.datagen snapshot                            # G12 (asks for confirmation with a cost estimate)
python -m keeper.datagen stats                               # rates, counts, sizes
./run.sh --generate-data                                     # wraps run + validate + snapshot, with prompts
```

After a successful run: `git add data/ && git commit -m "data: regenerate demo (seed 20261025, profile full)"`. See [Data folder and git](08-data-folder-and-git.md).

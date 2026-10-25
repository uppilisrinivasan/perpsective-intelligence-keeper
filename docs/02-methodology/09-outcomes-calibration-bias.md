# Outcomes, calibration and bias

> "Part of any residual is insight, part is bias and part is noise. Holding a perspective lightly becomes a calibration problem." (IP §4)

## 1. Outcomes (L5, code only)

| Outcome | Derived from | Window |
|---|---|---|
| `merged` | `pull.merged_at` not null | — |
| `closed_unmerged` | `state = closed` and `merged_at` null | — |
| `reverted` | (a) a PR whose title matches `^Revert "` and whose body contains `Reverts <owner>/<repo>#<n>` (the format GitHub's revert button writes); or (b) a commit on the default branch whose message contains `This reverts commit <sha>.` (the format `git revert` writes), where `<sha>` is the PR's merge commit or one of its commits | `revert_window_days` (90) |
| `post_merge_bug` | An issue labelled with a label in `bug_labels` (`bug`, `regression`) created after the merge, **and** either (a) the issue body or timeline cross-references the PR, or (b) the issue is closed by a PR whose diff modifies lines that this PR added (via `git blame` at the fix PR's base) | `bug_window_days` (120) |
| `follow_up_fix` | A later merged PR, by anyone, modifying ≥ 30% of the lines this PR added, within the window, whose title or body matches `fix|correct|handle` (configurable regex) | `follow_up_window_days` (60) |
| `ci_failed` | The check run conclusion is `failure` at the PR head when merged | — |

**Linking outcomes to findings (`outcome_links`).** A bad outcome (`reverted`, `post_merge_bug`, `follow_up_fix`) is linked to a finding on the same PR if the outcome's touched lines (from the revert or fix diff, mapped back to the PR's new-side lines) overlap the finding's anchor ± `line_window`, or the finding is PR-level or file-level on a touched file, **and** the category is compatible (`config/taxonomy.yaml` `outcome_compat`; for example a `post_merge_bug` is compatible with correctness, security, invariant, performance and api_compat). Each link stores its evidence.

## 2. What "the concern was ignored" means

For a finding f on a merged PR:
- **Addressed:** a commit after f's `created_at` and before the merge modifies lines within f's anchor ± `line_window`, or f's thread has a reply from the author with an acknowledgement (classified by `extract_findings` as `kind = social` with `ack: true`). This is derived by code where possible.
- **Ignored:** not addressed, and the PR merged.

Only **ignored** concerns can test a prediction: if a concern is raised and fixed, nobody learns whether it would have mattered.

## 3. Per-item calibration (L7)

For a lens item I (any type), consider the training PRs where I's **triggers fire** and the PR merged. For each such PR, the item's concern is either:

- *present and ignored*: someone's finding matching I (human, baseline, or the lens applied retrospectively) was ignored, or nobody flagged it;
- *present and addressed*;
- *absent*: no finding matching I.

Per item:

```
n_ignored  = PRs where I's concern was present and ignored
k_bad      = of those, PRs with a bad outcome linked to a finding matching I
posterior  = Beta(α0 + k_bad, β0 + n_ignored − k_bad)       # α0, β0 = config lens.prior (1, 3): a sceptical prior, mean 0.25
hit_rate   = posterior mean;  ci90 = Beta quantiles (0.05, 0.95)
base_rate  = bad-outcome rate among all merged PRs touching the same files
lift       = hit_rate / base_rate
```

**Why retrospective lens application is allowed here:** to count "present" for edge items on PRs P did not flag, Keeper applies the lens version under calibration to training PRs. This uses training data only, so it is not leakage into Proof. It is marked in `build_stats` as `retro_applied_prs`.

**Status effects** (`config/lens.yaml` `calibration.*`):
- An `edge` item stays `validated` if `n_ignored < min_outcome_n` (3); there is not enough outcome data, and the UI says "Proven by your reviews; not yet by outcomes".
- An `edge` item with `n_ignored ≥ min_outcome_n` and `ci90.upper < base_rate` becomes **`candidate`**, with the note "When this was ignored, nothing bad followed more often than usual".
- A `blind_spot` item requires `k_bad ≥ blind_spot_min_bad_outcomes` (2) **and** `lift ≥ blind_spot_min_lift` (1.5).
- Cost weight `w(I) = hit_rate × mean_severity_weight` (severity weights blocker 3, major 2, minor 1, nit 0.25). It is used in Find and in Practice ("costly misses").

**Explanations (`calibration_notes`, `deep` model, Batch API when enabled).** For each item whose status changed, or whose CI changed by > 0.1, the model writes a two-sentence plain-language explanation from the numbers and the linked outcomes ("You flagged unclosed file handles twice; when others ignored it, 2 of 3 times a bug report followed (#301, #355)."). The model receives only computed numbers and outcome titles. It cannot change statuses.

## 4. Recalibration schedule

- On demand (Lens → **Recalibrate**), after a lens rebuild, and as a scheduled job (`schedule.recalibrate_cron`, default weekly) when running on Nebius (`JOB_RUNNER=nebius`, a Serverless Job).
- Recalibration updates `stats` and `status` **in place on a copy**: it produces lens version v+1 with `change_reason = recalibration`, so history stays immutable.

## 5. The group-tracking bias check (FR-CAL-5, FR-CAL-6)

> "Concern that tracks a patient's group rather than their condition is flagged as bias." (UC §2), transposed to contributors.

For each `edge` item I of person P:

1. **Population:** training PRs reviewed by P where I's triggers fire.
2. **Groups:** the PR author's `author_association` collapsed by `bias.groups` (default: `newcomer` = FIRST_TIME_CONTRIBUTOR, FIRST_TIMER, NONE; `regular` = CONTRIBUTOR, COLLABORATOR, MEMBER, OWNER).
3. **Strata:** PR size bucket (changed lines ≤ 20, ≤ 100, > 100) × top-level area.
4. **Statistic:** a Mantel–Haenszel pooled odds ratio of "P flagged I" for newcomer versus regular across strata, with a 95% CI (Robins–Breslow–Greenland variance). Implemented in code with `numpy` and `scipy.stats`.
5. **Outcome check:** the same comparison for "bad outcome given I ignored", if `n ≥ min_outcome_n` in both groups.

An item is **`bias_suspected`** when OR ≥ `bias.or_threshold` (2.0), the CI's lower bound is > 1, there are ≥ `bias.min_per_group` (5) PRs in each group, **and** the outcome check shows no matching difference (or has too little data). The owner sees:

> **Possible bias.** For similar changes, you ask newcomers about *tests for every branch* 3.1× as often as regular contributors (14 vs 6 PRs; 95% CI 1.4–6.8×). When this was skipped, bugs did not follow more often for newcomers. Keeper won't apply this item to newcomers' PRs as "your eye". [Keep it anyway] [Turn it off] [Learn more]

"Keep it anyway" sets `owner_override = keep` and records the decision. The item then applies to all authors. It is never silently applied to only one group.

**Why this is the right check.** It compares like with like (strata), it needs outcome support before calling something insight, and it states its uncertainty. It cannot prove bias. The UI says "possible".

## 6. Calibration in the UI

Every number shows its n. Below `min_support`, it shows "Not enough evidence yet". Credible intervals are shown as a bar with the range, never as bare point estimates.

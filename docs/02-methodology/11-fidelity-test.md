# The Perspective Fidelity Test

> "Hold out situations a person has already judged. A lens passes if it predicts what that person noticed better than the baseline alone does, and does so without exaggerating the person's most obvious traits." "Sounding like you is easy. Noticing like you is the test." (IP §7)

## 1. Protocol

| Element | Specification | Config (`config/fidelity.yaml`) |
|---|---|---|
| Person | P with a lens version v | — |
| Ruler | v's ruler; it must equal the run's ruler | — |
| Held-out set | PRs with `created_at ≥ v.cutoff_at` and `< holdout_end`, reviewed by P with ≥ 1 substantive finding; drafts and bots excluded | `holdout.min_findings: 1` |
| Leakage controls | v was built with PRs `< cutoff_at` only; exemplar retrieval per PR uses findings with `created_at < pr.created_at` **and** `< cutoff_at` (strict; the run's option `allow_rolling_exemplars: false`) | `leakage.*` |
| Systems compared | **Baseline** (C), **Lens** (L), **Keeper** (L ∪ the C findings routed to `shared` or `blind_spot`: what the user actually sees in the main view) | — |
| Unit of analysis | PR (for bootstrap), finding (for rates) | — |
| Matching | [Matching](04-matching-and-residual.md) of each system's findings against H(S) | — |

Demo default: v1 (cutoff = history end − 6 months), held-out = the last 6 months (about 40 PRs).

## 2. Metrics

For each system X ∈ {Baseline, Lens, Keeper}, over held-out PRs S:

| Metric | Definition | Better |
|---|---|---|
| **Substantive recall** | Σ_S matched_weight(H_S, X_S) ÷ Σ_S abs(H_S) | ↑ |
| **Residual recall** (Lens, Keeper) | Of P's findings on S that the baseline missed (R+ under the ruler), the share X recovers. The baseline's residual recall is 0 by construction. | ↑ |
| **Noise per PR** | X findings matched to neither H nor a linked bad outcome, per PR | ↓ |
| **Precision** | (X findings matched to H or to a linked bad outcome) ÷ abs(X) | ↑ |
| **Per-category recall** | Recall restricted to each category | — |
| **Caricature ratio** | For P's top-3 categories by frequency in H (over the held-out set): `rate_X(c) / rate_H(c)`, where rate = findings in c per PR. Report the max over the 3. | close to 1; ≤ `caricature.max_ratio` (1.3) |
| **Category JSD** | Jensen–Shannon divergence between the category distributions of X and of H | ↓ |
| **Routing accuracy** (demo only) | PR lanes against the ground-truth lanes; macro-F1 | ↑ |
| **Unknown-lane recall** (demo only) | Share of ground-truth `unknown` PRs routed to `unknown` | must equal 1.0 |

*Why caricature is measured on top categories:* the signature of caricature (Cheng et al., 2023) is exaggerating the most obvious traits. A lens that flags security on every PR because P often does would score well on security recall, but its security rate would far exceed P's.

## 3. Uncertainty and comparison

- **95% CIs** by a percentile bootstrap over PRs (`bootstrap.n` 2,000, `bootstrap.seed` 13).
- **Paired comparison** of Keeper against the baseline on substantive recall: a bootstrap of the per-PR differences. Report the mean difference and its CI, and p = the share of resamples ≤ 0.
- **Sensitivity rows:** recall with `line_window` 3 and 10; recall counting `partial` as 0 and as 1.

## 4. Pass criteria (`config/fidelity.yaml` `pass.*`)

A run **passes** when all hold:
1. Keeper's substantive recall exceeds the baseline's, and the paired difference's CI lower bound is > 0.
2. Keeper's noise per PR ≤ the baseline's noise per PR × `pass.max_noise_ratio` (1.0).
3. Lens caricature ratio ≤ `caricature.max_ratio`, and the lens JSD ≤ the baseline JSD.
4. Demo only: unknown-lane recall = 1.0.

The UI shows each criterion as a pass or fail line, and the overall verdict in plain words: "Keeper sees like Mira on PRs it never saw" or "Not yet: Keeper doesn't beat generic review here". It never hides a fail.

## 5. Falsifiers shown as live checks (FR-FID-9)

From IP §10 and UC §5 ("What would prove us wrong"):

| Falsifier | Computed as | Shown as |
|---|---|---|
| The residual is mostly noise | Residual recall of the lens ≤ `falsifier.noise_floor` (0.1) | "The residual predicts something: ✓ / ✗" |
| Lenses do not transfer | Lens recall ≤ baseline recall on held-out | "The lens beats generic review on unseen PRs" |
| Fidelity collapses into caricature | Caricature ratio > threshold | "No exaggeration of Mira's favourite concerns" |
| Perspective is just preference | Shown as not testable in v1, with the reason | "Not tested in this version" |
| AI shrinks the people it learns from | Growth: R+ per PR of P falling across periods while R+ hit rate holds (see Growth) | "Mira's own edge is holding" |
| Help hollows | Practice: after-check recall < before-check recall for the demo learner cohort | "Practice doesn't make learners worse unassisted" |
| The loop grows contrarians | R+ rising while the R+ hit rate falls | "Edge growing without losing accuracy" |
| Perspective loses value as AI improves | Not testable in v1 (needs model generations) | "Not tested in this version" |

## 6. Execution

- `POST /api/v1/projects/{pid}/fidelity-runs` creates a job. Steps: build the held-out list → for each PR (concurrency `LLM_MAX_CONCURRENCY`), get the cached baseline or compute it, then lens recall, lens review and matching (L vs H, C vs H, L vs C) → metrics → bootstrap → falsifiers → persist.
- With `BATCH_API_ENABLED=true`, lens recall and lens review requests for all PRs are submitted as one Token Factory batch (OpenAI-compatible batch format: a JSONL of requests uploaded via `/v1/files`, then `/v1/batches` [verify]). Matching runs online after. The job polls the batch every `batch.poll_seconds` (20).
- Cost estimate before running: number of PRs × per-PR cost from [Applying the lens](06-applying-the-lens.md) §5, plus matching. Shown in the confirmation.

## 7. Real-repository runs

For an imported repository, the same protocol applies with `holdout` = the last `holdout_months` (6) of the import window. There is no ground truth, so routing accuracy is omitted. The result is reported whatever it is (BR-7). The README reports it as "On <repo> (public review history of <maintainer>, used for evaluation with attribution): …".

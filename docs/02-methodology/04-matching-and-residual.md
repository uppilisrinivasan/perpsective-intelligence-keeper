# Matching and the residual: R(S) = H(S) − C(S)

## 1. The problem

Two reviewers rarely phrase the same concern the same way or anchor it on the same line. "Subtraction" of finding sets therefore needs a **matching**: deciding which finding in set A expresses the same concern as which finding in set B.

Matching is used for:

| Pair | Purpose |
|---|---|
| H vs C | The residual: learning the lens, the edge map, calibration |
| H vs L (lens findings) | Fidelity, the growth residual G |
| L vs C | Routing a live PR (shared versus edge versus baseline-only) |
| Learner vs H | Practice scoring (with the `practice_score` prompt, which adds feedback) |

## 2. Algorithm

`keeper.residual.match(A, B, pr) -> Matching`

**Step 1 · Candidate generation (code).** For each a ∈ A and b ∈ B (substantive findings only, unless both are style), form a pair if any of these holds:
- the same path and the line ranges overlap after padding each by `line_window` (6);
- both are PR-level, or one is PR-level and the other is in a file the PR-level statement mentions;
- the same path and the same category (file-level match);
- TF-IDF cosine of the statements ≥ `min_lexical` (0.35), whatever the anchor.

Pairs are scored `pre = 0.5·anchor_score + 0.3·lexical + 0.2·[same category]`, where `anchor_score` is 1 for overlap, 0.6 within the window, 0.3 for the same file and 0 otherwise. At most `max_candidates_per_finding` (4) top candidates are kept per finding.

**Step 2 · Judge (`match_findings`, `judge` model, temperature 0).** One call per PR with all candidate pairs (batched in groups of ≤ 30). For each pair the judge returns:

```json
{"pair_id": "p7", "decision": "match", "same_concern": true, "rationale": "Both say the resolved include path is not confined to root."}
```

`decision` ∈ `match` (the same concern; either would satisfy the other reviewer), `partial` (overlapping but one is broader, or the same location with a different concern that would likely be fixed together), `none`.

**Step 3 · Assignment (code).** Build a bipartite graph with weights `match = 1.0`, `partial = 0.5`, and solve maximum-weight one-to-one assignment (`scipy.optimize.linear_sum_assignment`). Unassigned partial edges are dropped.

**Step 4 · Partition.**
- `shared` = assigned pairs with `match`, plus `partial` pairs, which count 0.5 in metrics and as shared in routing;
- `r_plus` = A findings not assigned;
- `r_minus` = B findings not assigned.

Invariant (tested): |A| = |shared_A| + |r_plus| and |B| = |shared_B| + |r_minus|.

## 3. Residual samples

For each reviewed PR and each person with a lens, L4 writes one `residual_samples` row per finding, with `{finding_id, pr, person, ruler_id, class: shared | r_plus | r_minus, matched_finding_id, weight}`. These samples are the training data of the lens. R− samples are attributed to the person whose H was used ("what the baseline saw that P did not").

**PRs P did not review are excluded** for P (no H, so no R).

**Shallow reviews.** If P's only activity on a PR was an approval with no comment, the R− samples on that PR get `weight = shallow_review_weight` (0.3). Approving without comment is weak evidence that P saw and dismissed the baseline's concerns.

## 4. Validating the judge

- **Demo:** the ground truth knows which planted maintainer comment corresponds to which slot, and the baseline's outputs are linked to slots by the slot validator (see [Ground truth](../03-data/07-ground-truth-and-validation.md) §4). Agreement between the judge's match decisions and slot equality is reported as Cohen's κ and accuracy, with a target κ ≥ 0.7 (`config/eval.yaml`).
- **Real imports:** Proof shows 20 random judged pairs for spot checks.
- **Robustness check:** Proof can re-run the fidelity metrics with `line_window` set to 3 and to 10 and report whether conclusions change (a sensitivity row in "How we measure").

## 5. Why not embeddings alone

Embedding similarity of short review statements conflates "the same file, a different concern" with "the same concern". A judge with location context is much more precise. Code pre-filtering keeps judge calls small (about one call per PR). Local TF-IDF is used for candidate generation so no embedding model is required. An optional embedding model is configurable (`EMBEDDINGS_PROVIDER`).

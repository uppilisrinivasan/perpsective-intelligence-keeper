# The lens: representation and building

> "A lens is anything that predicts R in situations the person has never seen." (IP §4)

## 1. Choice of representation (v1)

The idea paper lists candidates from lightest to heaviest: lens card, salience model, steering direction, low-rank adapter, skill. v1 uses a **structured lens (items) plus exemplar retrieval, rendered as a lens card and packaged as a skill**.

| Candidate | v1 decision | Reason |
|---|---|---|
| Lens card (human-readable) | **Yes**, generated from items | Inspectable; the owner can edit it; it reflects the lens back to them |
| Salience model (predicts what they would flag) | **Yes, implicitly**: items with triggers plus the lens review | Testable by the Fidelity Test |
| Steering direction | No | Needs self-hosted weights; out of scope (see [Beyond the hackathon](../09-deployment/05-beyond-the-hackathon.md)) |
| LoRA adapter | No | Self-service fine-tuning of the main Nemotron models is not listed on Token Factory; data is small; it would tangle seeing with style |
| Skill (lens plus procedures an agent can run) | **Yes**: the export package includes `SKILL.md` | Portable; owned |

## 2. The lens item

```jsonc
{
  "id": "itm_…",
  "lens_version_id": "lv_…",
  "type": "edge",                    // edge | blind_spot | shared_ground
  "title": "Include paths stay inside the project root",
  "statement": "When code resolves include or import paths from configuration files, check that the resolved path cannot escape the root directory (.., symlinks, absolute paths).",
  "rationale": "Config files may be untrusted; a traversal reads arbitrary files. An earlier fix (#212) missed symlinks.",
  "category": "security",
  "severity_typical": "major",
  "triggers": {
    "paths": ["strata/include*.py", "strata/resolve/**"],  // glob, matched on changed files
    "code_patterns": ["open\\(", "Path\\(.*\\)\\.resolve", "os\\.path\\.join"],  // regex on added lines
    "pr_features": {"touches_public_api": null, "min_changed_lines": null, "labels_any": []}
  },
  "exemplar_finding_ids": ["fnd_…", "fnd_…"],   // ≤ max_exemplars, the most representative
  "counter_example_pr_numbers": [318, 342],       // triggers fired, the person did not flag
  "stats": {
    "support": 23,                                 // R+ samples in the cluster
    "trigger_precision": 0.62,                     // P(person flags | triggers fire), training PRs
    "baseline_overlap": 0.08,                      // share of the cluster's PRs where C matched
    "outcome": {"bad_when_ignored": 3, "ignored": 4, "posterior_mean": 0.69, "ci90": [0.34, 0.92]},
    "first_seen": "2023-11-02", "last_seen": "2026-08-19",
    "by_group": {"FIRST_TIME_CONTRIBUTOR": {"fires": 5, "flags": 3}, "CONTRIBUTOR": {"fires": 9, "flags": 6}}
  },
  "status": "validated",             // validated | candidate | bias_suspected | retired | disabled_by_owner
  "owner_edits": [],                 // wording changes, with timestamps
  "provenance": {"ruler_id": "rul_…", "build_job_id": "job_…", "model_ids": ["nvidia/Nemotron-3-Ultra-550b-a55b"]}
}
```

### Item types

| Type | Built from | Used for |
|---|---|---|
| `edge` | Clusters of R+ (what P flags and the baseline misses) | Lens review; the `edge` lane |
| `blind_spot` | Clusters of R− with outcome evidence (the baseline flagged it, P did not, and something bad followed) | Promoting baseline-only findings to `blind_spot` |
| `shared_ground` | Categories and areas where P's findings are mostly matched by C | The edge map's "generic review is enough here"; setting expectations |

## 3. Building a lens version (L6)

Input: person P, ruler, cutoff `T` (training uses PRs with `created_at < T`), and the residual samples and outcomes before T.

**Step 1 · Select samples (code).** Substantive R+ samples of P (weight ≥ 0.5), and R− samples with weight.

**Step 2 · Featurise (code).** For each sample: statement TF-IDF vector; category one-hot; path tokens (directory components, and the file stem split on `_`); code tokens from the anchored hunk (identifiers on added lines); kind and severity.

**Step 3 · Cluster (code).** Agglomerative clustering (cosine distance, average linkage) separately per category group, with a distance threshold of `cluster_distance` (0.55). Clusters below `min_cluster_size` (3) become a "misc" pool. Misc samples are offered to the model in step 4 to be attached to an item or left out.

**Step 4 · Name and describe (`lens_items`, `deep` model, one call per category group).** Input: the clusters, with ≤ 8 representative statements each (closest to the centroid), their paths, short hunks (≤ 15 lines each), the cited history refs, and the misc pool. Output per cluster: `title`, `statement`, `rationale`, `triggers.paths` and `triggers.code_patterns` (proposed), `merge_with` (to merge clusters), `exclude_sample_ids` (outliers). Rules: describe **what P notices and why**, generalised beyond the examples but not beyond the evidence; no claims about P's personality; ≤ 40 words per statement; triggers must be satisfied by ≥ 60% of the cluster's samples (code checks this and trims patterns that fail).

**Step 5 · Compute statistics (code).** For every item, on training PRs: `support`; `trigger_precision` (among training PRs reviewed by P where triggers fire, the share where P flagged a finding matching the item, using item-membership as the match); `baseline_overlap`; `counter_example_pr_numbers` (triggers fired, no flag); `by_group`; and outcome stats (see [Calibration](09-outcomes-calibration-bias.md)).

**Step 6 · Exemplars (code).** Up to `max_exemplars` (6) per item: the most central samples, preferring diversity of paths and recency, and preferring findings with clear statements.

**Step 7 · Blind-spot items.** Cluster R− samples the same way. Keep only clusters where the baseline's concern was followed by a bad outcome on the linked lines at least `blind_spot_min_bad_outcomes` (2) times. The `deep` model names them, using the same prompt with `type = blind_spot`.

**Step 8 · Shared-ground items.** For each (category, top-level path) cell with ≥ `shared_min_findings` (5) of P's findings, if the share matched by C is ≥ `shared_min_overlap` (0.7), create a `shared_ground` item (named by code from a template in the copy file; no model call).

**Step 9 · Status (code).** Apply the thresholds in `config/lens.yaml`:

| Status | Rule |
|---|---|
| `candidate` | support < `min_support` (4), **or** trigger_precision < `min_trigger_precision` (0.25) |
| `validated` | support ≥ `min_support`, trigger_precision ≥ `min_trigger_precision`, and not bias-flagged |
| `bias_suspected` | fails the group-tracking check (calibration §5) |
| `retired` | last_seen older than `retire_after_days` (540) **and** no trigger firing with a flag in that window |
| `disabled_by_owner` | set by the owner; carried over to new versions unless the owner re-enables it |

**Step 10 · History digest (code).** Build the long-context **history digest** used by lens recall: every substantive finding of P before T, as compact lines: `[fnd_id] #PR path:line category severity "statement" (item itm_id)`. About 40 tokens per line, so 700 findings ≈ 28k tokens, well inside Lightning's context. Stored with the version.

**Step 11 · Lens card (`lens_card`, `judge` model).** It writes `LENS.md` from the items: a 3-sentence summary, then sections *What you notice* (validated edge items), *Still learning* (candidates), *Blind spots worth knowing*, *Where generic review is enough*, *Possible bias* (owner-only section; excluded from exports unless the owner includes it). Every claim links to an item ID. The card is regenerated only for a new version.

**Step 12 · Persist** as an immutable `lens_version` with `{version, cutoff_at, ruler_id, item_ids, digest_sha, card_md, build_stats, created_at}`.

## 4. Style hints (for review drafts only)

Separately from the items, code computes **style hints** from P's comments: the median comment length, the share of comments with code suggestions (```` ```suggestion ```` blocks), the share phrased as questions, greeting habits, and the order of sections in review bodies. These shape the *format* of review drafts (FR-REV-3). They are never used for fidelity, and the Lens screen does not present them as part of "how you see".

## 5. Cost

One `lens_items` call per category group (about 8–10 calls), each ≤ 20k tokens in and 3k out, on Ultra: about $0.30 per build. The card is one Super call.

## 6. What this representation cannot do (published in Lens → "How this works")

- It captures what P flags in **text**. It cannot capture what P looks at without commenting.
- Items generalise from examples. A concern P has expressed only once or twice stays a `candidate`.
- It predicts P's concerns, not P's correctness. Calibration measures the latter.

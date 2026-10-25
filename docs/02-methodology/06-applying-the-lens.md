# Applying the lens to a pull request

Input: PR context block (A1), lens version `v` (with its cutoff and items), person P, ruler. Output: lens findings L(S), each citing items and exemplars.

## 1. A3 · Recall: which items and past reviews are relevant

Two complementary selectors run, and their results are united.

**1a · Trigger evaluation (code, always).** For each item of type `edge` or `blind_spot` with status `validated` or `candidate`:
- `paths` globs matched against the changed file paths (including `previous_filename` for renames);
- `code_patterns` regexes matched against added lines, and removed lines for `api_compat` items;
- `pr_features` evaluated on PR metadata.

An item **fires** if any path glob matches and (it has no code patterns, or any code pattern matches), or if a code pattern matches anywhere in the diff with ≥ 2 hits. Fired items get `recall_source = trigger`.

**1b · Long-context recall (`lens_recall`, `fast` model, Nemotron 3.5 Lightning).** This is the step the use-case paper assigns to Lightning: "hold the maintainer's review history and the pull request together".

- Input: the full **history digest** of the lens version, filtered to findings created before `pr.created_at`; the item list (ID, title, statement); and the PR context block.
- Output: `{"relevant_items": [{"item_id", "why"}], "relevant_findings": [{"finding_id", "why"}]}`, with ≤ 8 items and ≤ 12 findings, every ID from the input (code validates them).
- Budget: if digest plus PR exceeds `recall.max_context_tokens` (default 400,000, well under the 1M context, to control cost and latency), the digest is trimmed by dropping the oldest findings of items with ≥ 10 exemplars first.

**1c · BM25 fallback (code).** If the `fast` model is unavailable or the call fails, use BM25 over digest lines with a query built from the changed paths, the identifiers on added lines and the PR title. Take the top 12 findings and the items they belong to. The run log records `recall_mode = bm25`.

**Selected exemplars** for the review prompt = the union of the recall-selected findings and, for each fired item, its stored exemplars, filtered to `created_at < pr.created_at`. At most `review.max_exemplars` (16), with the diff hunk of each exemplar's original comment (≤ 12 lines) attached, so the reviewer sees concrete past situations.

## 2. A4 · Lens review (`lens_review`, `judge` model, Nemotron 3 Super)

The prompt has the **same** PR context block and output schema as `baseline_review`, plus a lens block:

```
<lens owner="Mira" version="v2">
  <item id="itm_12" type="edge" status="validated" category="security">
    <title>Include paths stay inside the project root</title>
    <statement>…</statement>
    <rationale>…</rationale>
  </item>
  … (fired and recalled items first, then other validated edge items in brief: id + title only)
  <blind_spot id="itm_40">Windows path separators and encodings in file APIs</blind_spot>
</lens>
<past_reviews>
  <exemplar id="fnd_881" pr="212" path="strata/include.py" date="2024-05-02" item="itm_12">
    <hunk>…</hunk>
    <said>Resolved include path can escape the root via '..'.</said>
  </exemplar>
  …
</past_reviews>
```

Instructions (abridged; full text in [Prompt catalog](15-prompt-catalog.md)):
1. Review the PR **as this person would**, using their lens items and past reviews as evidence of what they notice.
2. Return the findings this person would raise, including the routine ones they would raise. Do not invent concerns outside the evidence, except routine ones (style, tests) that the person demonstrably raises.
3. Every finding MUST cite ≥ 1 `item_id` (or `"routine"` for style and tests when the lens has a shared-ground item for it) and SHOULD cite the exemplar IDs that justify it.
4. Give `certainty` ∈ `low`, `medium`, `high`, and explain how this situation is like the cited past ones.
5. Do not output a finding for an item just because it fired. Only output it if the change actually has the issue.

## 3. Post-processing (code)

1. Validate the schema, the citations (IDs exist in the input) and the anchors (§2.1 of [Situations and findings](01-situations-and-findings.md)). Drop findings with no valid citation and count them (`dropped_uncited`).
2. **Confidence:**

   | Cited item status | Model certainty | Confidence |
   |---|---|---|
   | validated, posterior mean ≥ 0.6 | high | high |
   | validated | medium or high | medium |
   | validated | low | low |
   | candidate | any | low |

3. Merge duplicates (as in [Situations and findings](01-situations-and-findings.md) §2.2).
4. Attach to each finding: `refs.lens_item_ids`, `refs.exemplar_finding_ids`, and the `why_similar` text.

## 4. A5 · Lens versus baseline matching

Run [matching](04-matching-and-residual.md) with A = lens findings and B = baseline findings for the same head SHA. This drives routing (next document).

## 5. Cost per PR (typical)

| Step | Model | Tokens in / out | Cost |
|---|---|---|---|
| Recall | Lightning | ~35k / 0.6k | ~$0.002 |
| Lens review | Super | ~9k / 1.5k | ~$0.004 |
| Baseline review | Super | ~6k / 1.5k | ~$0.003 |
| Match | Super | ~3k / 0.5k | ~$0.001 |
| Triage signals | Lightning | ~6k / 0.4k | <$0.001 |
| Draft | Super | ~3k / 1k | ~$0.002 |
| **Total** | | | **≈ $0.012** |

A 12-PR queue costs about $0.15 before fixes.

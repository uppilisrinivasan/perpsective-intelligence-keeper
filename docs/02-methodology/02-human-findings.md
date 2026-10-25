# What the maintainer noticed: H(S)

## 1. Whose findings

`people` rows are created from every `user` object in the mirror. A person's **role** in a project is derived by code:

| Role | Rule (config `people.*`) |
|---|---|
| `maintainer` | Listed in the `MAINTAINERS` file or as a CODEOWNERS owner for `*`, **or** merged ≥ `maintainer_min_merges` (20) PRs of others. The demo marks exactly one primary maintainer in the manifest; imports take it from the user's input. |
| `reviewer` | ≥ `reviewer_min_reviews` (10) submitted reviews on others' PRs, and not a maintainer |
| `contributor` | Authored ≥ 1 PR |
| `bot` | `user.type == "Bot"`, or the login ends with `[bot]` |

Lenses can be built for any `maintainer` or `reviewer` with consent. The demo builds two: the primary maintainer and one security-minded reviewer (the "another lens").

## 2. Input units

For each PR and each person P (not the PR author, not a bot), Keeper gathers P's **review material**:

1. Review comments (`pulls/{n}/comments`) where `user.id = P`, grouped into **threads** by `in_reply_to_id` (the root is the comment without it).
2. Review bodies (`pulls/{n}/reviews`) where `user.id = P` and `body` is non-empty, plus each review's `state`.
3. Conversation comments (`issues/{n}/comments`) by P.
4. If P closed the PR unmerged (timeline `closed` event by P with `merged = false`): the last comment by P within `rejection_window_minutes` (60) of closing is a **rejection** candidate.
5. Commits on the PR whose committer login is P and whose date is after P's first review (`maintainer_fix` candidates; FR-H-5, could).

Replies by P inside threads that P did not start are included as context for the root, not as new units, unless the extractor says they raise a new concern (FR-H-4).

## 3. Extraction (`extract_findings`, `fast` model)

Call granularity: **one call per (PR, person)** containing all their units for that PR, so that the model can merge "same concern said twice" and resolve cross-references ("as I said above").

Input (all untrusted text is in fenced data blocks):
- the PR context header (title, files list; not the full diff);
- for each inline thread: the root comment's `diff_hunk` (as GitHub gives it), `path`, `line`, `side`, and the thread's comments by P with IDs;
- review bodies with `state`;
- conversation comments by P;
- a rejection candidate, if any;
- the taxonomy (category names and descriptions) and the severity and kind definitions.

Output schema (`config/schemas/llm/extract_findings.json`):

```json
{
  "findings": [
    {
      "source_ids": {"comment_ids": [884123], "review_ids": [], "issue_comment_ids": []},
      "anchor_hint": {"scope": "line", "path": "strata/include.py", "line": 47},
      "category": "security",
      "severity": "major",
      "kind": "change_request",
      "statement": "Resolved include path can escape the project root via '..' segments.",
      "rationale": "Includes come from untrusted files.",
      "suggestion": "Check resolved.is_relative_to(root).",
      "is_question_challenge": false
    }
  ],
  "non_findings": [{"source_ids": {"comment_ids": [884200]}, "reason": "social"}]
}
```

Rules in the prompt:
- Each source ID MUST appear in exactly one finding or in `non_findings`. Code checks this and re-asks once on violation.
- The statement is one sentence in the **reviewer's meaning**, neutral voice, ≤ 30 words. Do not invent concerns.
- `history_context` is used when the comment references a past PR, issue, commit, release or decision.
- Do not judge whether the reviewer was right.

Post-processing (code):
1. Anchors: from the source comment's fields (§2.1 of [Situations and findings](01-situations-and-findings.md)); `anchor_hint` is used only for PR-level units.
2. `substantive` = the category is not in `{style, social}`; for `question`, it equals `is_question_challenge`.
3. Severity is adjusted by the review state: a finding in a `CHANGES_REQUESTED` review is at least `major`.
4. References to `#123`, commit SHAs and release tags are resolved to existing PRs, issues and commits and stored as `refs.history_refs` (used by the lens as exemplars of `history_context`).

## 4. Why extraction instead of using raw comments

1. Raw comments mix several concerns, or none. Fidelity must count *concerns*, not messages.
2. Matching against baseline findings needs the same unit on both sides.
3. Categories feed the caricature check and the edge map.

## 5. Quality control

- **Demo:** the generator plants each maintainer comment from known concern slots, so the ground truth gives the true category and count per comment. `./run.sh --eval` reports extraction precision and recall against it (target ≥ 0.9 and ≥ 0.85, in `config/eval.yaml`).
- **Real imports:** a 30-comment sample is shown in Proof → "How we measure" with its extracted findings, so a human can audit it.

## 6. Cost control

- Only PRs with ≥ 1 human review unit are extracted.
- The cache key is (sorted source IDs, the bodies' hash, prompt version, model ID).
- On the demo data, about 600 calls × ~1.5k tokens on Lightning costs well under $0.20.

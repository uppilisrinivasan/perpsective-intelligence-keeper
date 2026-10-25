# Screen: Pull request

**Question answered:** "What would the maintainer say here, and can Keeper fix it?" **Primary action** depends on the lane: edge or blind spot → **Fix and test** (if fixable) or **Copy review**; unknown → **Hand to {name}**; shared → **Looks fine: copy approval note**. **Requirements:** FR-REV, FR-FB, FR-FIX, FR-TRI, FR-OUT.

## 1. Layout (≥ 64rem): split view

```
┌ ← Queue   #418 Support !include in YAML sources   ● Needs your eye · ~20 min   [Ask about this] ┐
│ kai-n wants to merge 3 commits into main · +142 −8 · 4 files · CI ✓                              │
│ Keeper's summary: "Adds YAML include support. Mira would likely ask for path containment and a   │
│ test for include cycles; the baseline model only noted the missing type hints."                   │
├───────────── Findings (38%) ──────────────┬──────────── [Diff | Compare] (62%) ──────────────────┤
│ ● Needs your eye (2)                       │ loaders/yaml.py                                        │
│ ┌ Include paths can escape the config dir ┐│  41  + def _resolve_include(base, ref):                │
│ │ high · security · loaders/yaml.py:44    ││  44  +     path = base / ref          ◀ finding card  │
│ │ Why: Mira asked for containment on #233 ││ ┌──────────────────────────────────────────────────┐ │
│ │ and #301 (2 past comments ▸)            ││ │ ● Include paths can escape the config dir         │ │
│ │ [Accept] [Edit] [Dismiss] [Fix and test]││ │   Suggested: resolve and check is_relative_to(base)│ │
│ └──────────────────────────────────────────┘│ └──────────────────────────────────────────────────┘ │
│ ● Worth a second look (1)                  │                                                        │
│ ● Handled for you (3) ▸ collapsed          │                                                        │
│ Other model notes (2) ▸ collapsed          │                                                        │
├────────────────────────────────────────────┴────────────────────────────────────────────────────┤
│ Review draft (Drafted by Keeper) ▸                 [Copy review] [Export ▾]                       │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘
```

At ≥ 120rem the review draft becomes a third pane on the right. Below 64rem: tabs **Findings | Diff | Draft**.

## 2. Header

- Back link (keeps the queue filter); the PR number and title (h1); `LaneBadge`; attention estimate.
- Meta line: author (with first-time and association tags), commit count, size, file count, CI status from `checks`; "View on GitHub" only if the project is not fictional (`html_url` uses the reserved demo host otherwise, so it is hidden).
- `SummaryCallout`: `summary_md` from the analysis (the `summary` field of the `triage_signals` prompt).
- `SignalChips` (if any): "New dependency", "Touches packaging", "First-time contributor", with tooltips explaining why each one raises attention.
- An "Analysed {relative} · lens v{n} · Saved run" provenance line, plus **Analyse again** (confirmable) in the overflow menu.

## 3. Findings pane

Grouped by lane in this order: edge, blind_spot, unknown signals (if the PR is unknown: a `HandoffCard` at the top), shared (collapsed), baseline_only (collapsed, labelled "Other model notes").

`FindingCard`:
| Part | Content |
|---|---|
| Title | `title` (one line) |
| Meta | severity pill, category, `path:line` link (scrolls the diff and flashes the line), confidence label ("Likely", "Possible", "Worth checking") with how it was derived in a tooltip |
| Body | `statement_md`; the **Why** line: lens items ("Mira's pattern: *safe include paths*") plus **past comments** (expand to quotes with PR links) or, for blind spots, "Mira has missed this kind of issue in 4 of 6 past cases" |
| Suggestion | `suggestion_md`, as a code-styled block if it is code |
| Actions | **Accept**, **Edit** (inline editor for text and severity), **Dismiss** (asks for an optional reason: "not relevant", "wrong", "already handled"), **Good catch** (blind-spot lane only), **Fix and test** (if `fixable`), **Ask about this** (opens Ask with the finding context) |
| State | After feedback: the card shows a state chip ("Accepted", "Edited", "Dismissed") with **Undo** for 10 s, then an Undo link |

An **Add what Keeper missed** button at the bottom opens a small form (file and line picker from the diff, text, category), which becomes a feedback event.

## 4. Diff mode

- `DiffView`: files list (a collapsible tree at ≥ 90rem, a dropdown below), unified view (side-by-side toggle at ≥ 90rem), syntax highlighting, sticky file headers, line numbers. Finding cards render inline under their anchor lines; file-level findings go under the file header; PR-level findings stay only in the pane.
- Large files (patch null or > 3,000 lines) show "Large diff: load anyway".
- Keyboard: `j`/`k` next/previous finding, `n`/`p` next/previous file, `w` toggle wrap.

## 5. Compare mode (the "aha" view)

The purpose: make the residual visible.

```
           What the baseline model said        │     What Mira's lens added
  ─────────────────────────────────────────────┼─────────────────────────────────────
  ✓ Missing type hints on _resolve_include ────┼──── (shared: both)          ● grey
  ✓ Broad except in loader                ─────┼──── (shared)                 ● grey
                                               │  ● Include paths can escape   ● orange (edge)
                                               │  ● No test for include cycles ● orange
  ● Unpinned YAML loader (blue: Mira usually misses this) │                    ● blue
```

- Two columns with connecting lines for matched pairs (SVG lines drawn between the card anchors, recomputed with a `ResizeObserver`; below 64rem the columns stack and pairs are shown as "matches: …" text).
- The header sentence: "The baseline found {b}. The lens added {edge} that Mira would raise; {blind} the model caught that Mira tends to miss."
- For held-out PRs (from Proof or the tour), a third column, **What Mira actually wrote**, is shown when available (from `/human-review`).
- A legend explains the colours. Each card links to its full finding in Diff mode.

## 6. Fix and test panel

Opened by **Fix and test** (the confirmable action) as a panel replacing the findings pane (Back returns to findings), with deep link `/pr/:n/fix/:fixId`.

```
Fix and test · Include paths can escape the config dir          Sandbox: local · $0.06 so far
 ✓ Sandbox ready (2 s)                     
 ✓ Tests before the fix: 118 passed
 Branch A                                    Branch B
  ✓ Plan: resolve() + is_relative_to check    ✓ Plan: reject absolute and .. refs
  ✓ Applied (2 files)                         ✓ Applied (1 file)
  ✗ Tests: 1 failed · test_include_nested     ✗ Tests: 2 failed
  ✓ Repair (attempt 2)                        ⟳ Repair (attempt 2)…
  ✓ Tests: 119 passed ★ keeps this branch
 ✓ Verified: addresses the finding
[View diff] [Download .patch] [Copy as suggestion]                    [Cancel]
```

- `FixTimeline` renders job events live (`useJob`). Each step can expand: plan text, apply errors, failing tests with messages, a test output tail (monospace, virtualised).
- The result: `DiffView` of the winning diff; actions **Download .patch**, **Copy as review suggestion** (formats GitHub ```suggestion blocks for single-hunk changes), **Add to review draft**.
- Failure states: "Couldn't find a passing fix in 4 tries", with the last failing tests and the reason, plus **Try again with notes** (an optional text field passed as `user_hint`).
- Sandbox notice: the provider and its isolation level, in plain words.

## 7. Hand-off card (unknown lane)

"Keeper won't guess here. **{signal summary}**. Suggested reviewer: **Theo** (security reviewer) — reviewed 14 dependency changes; their lens catches supply-chain issues." Candidates (expand: top 3 with reasons), OSV results ("tomli-w 1.0.0: no known vulnerabilities", or vulnerabilities listed with IDs and links), the drafted note to the reviewer, and the checklist. Actions: **Copy note** (the primary action), **Choose someone else**.

## 8. Review draft

`ReviewDraftPanel`: the editable markdown body, with inline comments listed (each linked to its line). The label is always "Drafted by Keeper". **Copy review** (markdown to the clipboard), **Export ▾**: markdown file, or GitHub review JSON ("to post it yourself with the GitHub API or CLI": a copyable `gh api` command template with placeholders, never a token). Edits autosave (`PUT`, debounced 800 ms) with a "Saved" indicator.

## 9. States

- No analysis: "Keeper hasn't analysed this PR yet." + **Analyse** (confirmable), or in no-key mode "Not in the saved results."
- Analysis running: the findings pane shows the stage list streaming (`analysis.step`); the diff is usable meanwhile.
- `model_output_invalid`: "The model's answer didn't pass checks. Try again." with retry.

# Screen: Lens

**Question answered:** "What has Keeper learned about this maintainer, where does it matter, and can I control it?" **Primary action:** read the card. When unconsumed feedback exists: **Update lens**. **Requirements:** FR-LENS, FR-FIND, FR-CAL, FR-GOV, FR-GROW.

## 1. Header (shared by all tabs)

```
Mira's lens · v2 (19 Oct) ▾        ● Healthy                       [Update lens: 12 new signals] [⋯]
Learned from 214 reviewed PRs (Oct 2023 – Apr 2026) · ruler: Nemotron 3 Super, pinned · Saved run
[Card] [What it notices] [Where it matters] [Versions] [Growth] [Controls]
```

- The person selector (when more than one lens exists, for example Mira and Theo) and the version selector (`?v=`).
- `HealthBadge`: the health state with its plain sentence in a tooltip; it links to Growth.
- **Update lens** appears when feedback is unconsumed (count of feedback events); confirmable; opens the job, and when finished routes to the Versions diff.
- The overflow menu: Rebuild, Recalibrate, Export, and "Ask about this lens".

## 2. Tab: Card (default)

The lens card in plain language (`card_md`, rendered from `lens_card` output), in second person when viewing as the owner and third person otherwise. Each bullet has item chips (hover: the item statement and support). Below it, three **KeyFacts**: items count (by type: edge patterns, blind spots, style), precision across active items (with interval), and "last confirmed by a review" date.

## 3. Tab: What it notices (items)

- Filters: type (edge, blind_spot, style, standards), category, status (active, muted, low_confidence), and search.
- `LensItemCard` grid (`auto-fit`, `minmax(min(100%, 22rem), 1fr)`): title, type colour, category, statement, a `SupportMeter` ("seen in 9 reviews · right 82% of the time (65–93%)"), triggers as chips (paths, keywords), and a bias warning if any.
- Item detail (a side sheet at ≥ 64rem, a full page below): statement and rationale; **exemplars** (past comments as quotes with PR links and the hunk); counter-examples ("times this didn't matter"); stats over time; bias check result (in plain words: "No sign this fires more for first-time contributors" or a warning with the numbers); triggers; history across versions.
- Owner controls on an item: **Mute** (stops it from being used), **Edit wording**, **This is wrong** (mutes it and records the reason). Each edit shows "Takes effect on the next analysis".

## 4. Tab: Where it matters (Find edge map)

```
Where Mira's eye matters most                         Where generic review is enough
┌──────────────────────────────────────────┐          ┌─────────────────────────────────┐
│ strata/include · security       ███ high │          │ docs · style            ✓ enough │
│ "3.4× more than generic review"          │          │ strata/cli · correctness          │
│ 2 bad outcomes after merges ▸            │          └─────────────────────────────────┘
│ strata/merge · correctness      ██▌      │          Nobody looks closely here
│ …                                        │          ┌─────────────────────────────────┐
└──────────────────────────────────────────┘          │ strata/plugins (busy, few notes) │
                                                      └─────────────────────────────────┘
[Show full map]  → EdgeMap heatmap: areas (rows) × categories (columns), cell = value (orange intensity)
```

- `EdgeTopList` (top cells, ≤ 6): the area, the category label, the multiplier sentence, bad outcomes (expand: linked issues and reverts), the lens items involved, and "Open PRs touching this now: #418".
- `EnoughList` and `GapList`.
- The full `EdgeMap` heatmap is a CSS grid with a sticky header and row labels, horizontally scrollable on small containers. Cells are buttons (the accessible name gives area, category and value). Colour intensity uses 5 stepped edge tints, plus a text value on hover or focus, plus a pattern for "enough" cells so colour is never the only cue.

## 5. Tab: Versions

- A timeline list: each version with date, reason ("12 feedback signals", "recalibration", "initial build"), the counts of items added, removed and changed, and the origin.
- **Compare**: pick two versions → `LensDiffView`: the summary bullets (`lens_diff_summary`), then Added (green edge), Removed (strikethrough), Changed (field-level before/after, with stats deltas). Each item links to its detail.
- After an update job: lands here with the new version preselected against its parent, plus the message "v3 is now active" and **Undo** (re-activates the parent, recorded in the audit).

## 6. Tab: Growth

- The health state card with its explanation and what to do next (from the health rules).
- `GrowthTrend`: per period (quarter), small CSS bars for `r_plus_rate`, `costly_r_minus_rate`, `r_plus_hit` and G, with tooltips defining each in plain words.
- Practice results (if the person practised): before/after with G, linking to Practice.
- "insufficient_data": "Not enough recent reviews to tell" and what would be needed.

## 7. Tab: Controls

- Consent: the status, who granted it, when, and the text version; for real imported people, **Record consent**.
- Sharing: "Use this lens for project triage" (on by default for the owner in demo).
- **Pause** (stops use in triage; data kept), **Resume**, **Export** (downloads the JSON package), **Import a lens package**, **Revoke** (danger zone: a typed confirmation "REVOKE"; it deletes items and digests, keeps an audit stub, and the queue falls back to baseline-only with every PR marked "Needs your eye").
- The audit trail (last 50 events).

## 8. States

- No lens (imported project, or consent missing): explains why, and **Build lens** (confirmable) or **Record consent**.
- Building: the stage list (`lens.stage` events) with "This takes about 10 minutes. You can keep using Keeper."
- Paused: a banner across all tabs: "Paused: Keeper isn't using this lens. **Resume**."

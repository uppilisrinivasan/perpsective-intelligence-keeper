# UX principles and information architecture

## 1. Principles

1. **Answer first.** The top of every screen states the answer in one sentence ("4 of 12 pull requests need you. About 55 minutes."). Details come below.
2. **One primary action per view.** It is visually primary (filled button). Everything else is secondary or in a menu.
3. **Plain words in the UI; precise words in tooltips.** The UI says "Needs your eye", and the tooltip explains "R+: what Mira notices that the baseline model misses". Glossary terms have a dotted underline and a tooltip, from `GET /glossary`.
4. **Colour means who.** Orange = the maintainer's eye (edge). Blue = the model alone (blind spot). Grey = handled (shared). Violet = another reviewer (unknown). This matches the idea paper's figures. Colour is never the only signal: each lane also has an icon and a label.
5. **Show the evidence.** Each Keeper claim links to the past comments or the lens item behind it ("Because Mira said this on #233 and #301").
6. **Nothing happens without the user.** Keeper drafts, suggests and tests; the user decides. Actions that cost money show the estimate first.
7. **Live or saved is always visible.** A badge in the top bar and on each result says "Live" or "Saved run · 19 Oct".
8. **Conversation where it helps.** Questions ("why?", "what changed?", "what would Mira say?") go to Ask, which is available everywhere as a drawer. Structured work (reading a diff, comparing, practising) gets a purpose-built screen.
9. **No dead ends.** Every empty state says why and offers the next step. Every error says what happened and what to do.
10. **Fast to feel.** Show the skeleton within 100 ms, prefetch on hover, stream long work with visible steps.

## 2. Destinations

The judge's mental model is a loop: **see the queue → open a PR → trust why → (fix) → see the lens behind it → see it proven → try it yourself.** The navigation follows it.

| # | Destination | The question it answers | Contains (combined) | Why combined, or why separate |
|---|---|---|---|---|
| 1 | **Queue** (home) | "What needs me today?" | Answer header; lane summary with budget; the PR list, filterable by lane; a hand-off chip on unknown rows; the queue digest | Triage is one decision, so it gets one screen. The lane filter replaces four tabs. |
| 2 | **Pull request** (from the Queue, not in the nav) | "What would the maintainer say here, and can Keeper fix it?" | Summary and lane; findings grouped by lane; **Diff** view with inline findings; **Compare** view (baseline versus lens); review draft; fix and test; hand-off | Everything about one PR in one place. Modes (Diff or Compare) instead of pages, so context is never lost. |
| 3 | **Ask** | "Anything, in my words" | Thread list; chat; suggested prompts; action cards | Open-ended questions belong in a chat, not a dashboard. It is also a drawer on screens 1, 2, 4, 5 and 6. |
| 4 | **Lens** | "What has Keeper learned about this maintainer, and can I control it?" | Lens card (a readable summary); items; **Where it matters** (Find edge map); versions and diff; growth and health; controls (pause, revoke, export, consent) | One person's lens is one object. Its sub-views are tabs within the page because they share the version selector. |
| 5 | **Proof** | "Is the lens actually faithful?" | Verdict header; three-system comparison (maintainer, baseline, lens); metrics with intervals; falsifiers; case browser | Separate from Lens: it answers a different question (trust), and judges look for it explicitly. |
| 6 | **Practice** | "Can I learn to notice what the maintainer notices?" | Taste test (1 PR); the full Growth Test (before, learn, after); feedback per item; growth result | Separate: it is a different user (a learner) and a different mode (doing, not reading). |
| 7 | **Settings** (bottom of the nav) | "Is it set up; what has it cost?" | Models and probe; usage and caps; sandbox; projects and import; preferences | Operational, rarely visited. |

**Not top-level:** fix runs (inside the PR), hand-offs (inside the PR and Queue), jobs (a toast plus inline progress, with a "Recent activity" popover in the top bar), and versions (inside Lens).

## 3. Flows

### 3.1 The judge's first five minutes (the tour follows this)
1. The aha PR (a held-out PR chosen from data) in Compare: the baseline missed it, the maintainer caught it, and the lens caught it too, with the past comment as evidence.
2. Fix and test on a finding: watch the tests fail, the repair, then pass.
3. Queue: "4 of 12 need you." The tour highlights an unknown row ("Keeper won't guess here: it asks another reviewer").
4. Lens → Where it matters: the maintainer's edge map.
5. Proof: "The lens recovers 3× more of what Mira notices than the baseline" (actual numbers from data), with the falsifiers passing.
6. Practice → taste: try one PR yourself.

### 3.2 The maintainer's daily loop
Queue → open an edge PR → accept or edit findings → copy the review draft → next. Feedback accumulates. Lens shows "12 new signals: Update lens" → diff → accept.

### 3.3 The contributor's loop
Role picker → Contributor → Practice → before → learn (feedback with lens items) → after → see G.

## 4. Role picker

A top-bar menu: **Viewing as: Mira (maintainer)** | Theo (security reviewer) | Sam (contributor) | Me (judge). The names come from `GET /projects/{pid}/people`. It changes `X-Keeper-Role`, which lens is shown in Lens, and the default learner in Practice. Actions not allowed for the role are disabled with a tooltip ("Only the lens owner can pause it").

## 5. Navigation shape

- At ≥ `lg` (≥ 1024 px viewport): a left rail with icons and labels (collapsible to icons only; the preference is persisted).
- Below `lg`: a top bar with a menu button opening the same navigation as a sheet. Below `sm`: a bottom tab bar with Queue, Ask, Lens, Proof and More.
- Keyboard: `g q` Queue, `g a` Ask, `g l` Lens, `g p` Proof, `g r` Practice, `g s` Settings, `/` search or the Ask input, `?` the shortcuts sheet. All shortcuts are listed in the `?` sheet and in tooltips.

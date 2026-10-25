# App shell, navigation and the guided tour

## 1. Shell anatomy (≥ 64rem)

```
┌───────┬───────────────────────────────────────────────────────────────────────────┐
│ ◉     │ strata · acme-oss        [Live ●]  [Viewing as: Mira ▾]  [⟳ 1]  [? Tour] [Ask] │  ← TopBar
│ Queue │───────────────────────────────────────────────────────────────────────────│
│ Ask   │ (Banner area: no key / spend cap / fallback model / sandbox fallback)        │
│ Lens  │───────────────────────────────────────────────────────────────────────────│
│ Proof │                                                                           │
│ Practice│                         <route outlet>                                 │
│       │                                                                           │
│ ───── │                                                                           │
│Settings│                                                                          │
└───────┴───────────────────────────────────────────────────────────────────────────┘
```

| Element | Behaviour |
|---|---|
| Logo + "Keeper" | Links to the Queue |
| **NavRail** | Items with an icon, label and an optional count (Queue: the number needing attention; Lens: a dot when a lens update is available) |
| **ProjectLabel** | `owner/repo`; a switcher if there is more than one project; a "Demo world" tag when `fictional` |
| **ModeBadge** | `Live` (green dot) when the key is configured and the probe is OK; `Saved results` (grey) in no-key mode, with a popover explaining what works and how to add a key |
| **RolePicker** | See [UX and IA](01-ux-principles-and-ia.md) §4 |
| **ActivityButton** | The count of running jobs; a popover listing recent jobs with progress, cost and links |
| **TourButton** | Restarts the tour |
| **AskButton** | Opens the Ask drawer with the current context attached |
| **BannerArea** | At most one banner at a time, in priority order: spend cap reached > no key > model fallback active > sandbox fallback. Each is dismissible per session except the spend cap. |
| **Toasts** | Bottom-right (bottom-centre on phones): job finished or failed, with "Open" |

## 2. Shell states

| State | Shell behaviour |
|---|---|
| Loading `/status` (first paint) | Skeleton shell; the nav is visible; content skeleton |
| Status unreachable | A full-page "Keeper's server isn't responding" with retry and the `./run.sh` hint |
| Cloud mode without a session | Redirect to `/signin` (a single field: access code) |
| Data still loading (the `load_demo` job is running) | The content area shows "Setting up the demo world…" with the job steps |

## 3. The guided tour

**Goal:** in about 3 minutes, someone new understands what Keeper does and sees the proof, with no reading of documentation.

- **Start:** on first visit (`localStorage["keeper.tour.v1"]` absent), a centred welcome card appears: "Keeper learns what one maintainer notices in code review that AI misses, and uses it on their queue. Take the 3-minute tour?" with **Start tour** and **Explore on my own**.
- **Steps** come from `GET /tour` (data-driven: the PR numbers, item IDs and figures are chosen by `keeper.services.tour`). The default sequence:

| # | Route | Spotlight target | Copy pattern (values from data) |
|---|---|---|---|
| 1 | `/pr/{aha}?view=compare` | The R+ finding pair, with the third column "What {maintainer} actually wrote" | "A past PR Keeper never trained on. Generic review missed this; {maintainer} caught it, and so did {maintainer}'s lens, because of what they said on #{evidence_pr}." |
| 2 | `/pr/{fix_demo}/fix/{fix_id}` | The fix timeline | "Keeper wrote the fix {maintainer} would ask for and ran the tests. The first try failed; the second passed." |
| 3 | `/queue` | The lane summary | "Today's queue: {open_count} open PRs. Only {need_count} need {maintainer}: about {minutes} min. The rest are handled or handed off." |
| 4 | `/queue` | An unknown row | "This one is outside what Keeper knows about {maintainer}: {signal}. So it suggests {reviewer} instead of guessing." |
| 5 | `/lens?tab=map` | The top edge cells | "This is where {maintainer}'s eye matters most, and where generic review is enough." |
| 6 | `/proof` | The verdict header | "Tested on {holdout_count} PRs the lens never saw: it recovered {lens_recall}% of what {maintainer} noticed, against the baseline's {baseline_recall}%." |
| 7 | `/practice` | Start taste | "Your turn: can you spot what {maintainer} would?" |

The step count shown is the number of steps returned (7 by default; `config/ui.yaml` `tour.steps` can reorder or disable steps).

- **Spotlight:** a dimmed overlay with a cut-out around the target (`data-tour="…"` attributes), plus a popover with **Back**, **Next**, a step count and **Skip**. Esc skips. If a target is missing (for example no fix run in the data), the step is dropped by the server, not by the client.
- **Order:** the tour follows the demo story in [Solution overview](../00-start-here/01-solution-overview.md) §7: the aha comes first (within the first 30 seconds), then the build, then triage, then the proof.
- **No-key mode:** every step works from the snapshot; step 2 shows the saved fix run labelled "Saved run".
- **End:** "That's the loop: find, build, grow. Ask me anything." The Ask drawer opens with three suggestions.
- **Restart:** the Tour button. Progress is not persisted mid-way; a restart starts at 1.

## 4. Global keyboard and focus

- Shortcuts: see [UX and IA](01-ux-principles-and-ia.md) §5. They are disabled while typing in inputs.
- A route change moves focus to the page's `h1` and announces the title through a polite live region.
- A skip link ("Skip to content") is the first focusable element.

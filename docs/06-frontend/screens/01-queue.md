# Screen: Queue (home)

**Question answered:** "What needs me today?" **Primary action:** open the top PR that needs attention. **Requirements:** FR-Q, FR-TRI.

## 1. Layout (≥ 64rem)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 4 of 12 pull requests need you · about 55 min of your 120-min week               │  AnswerHeader (h1)
│ Keeper handled 5 and suggests another reviewer for 2.      [Refresh queue ⟳ $0.04] │
├──────────────────────────────────────────────────────────────────────────────────┤
│ [All 12] [● Needs your eye 4] [● Worth a second look 1] [● Needs another reviewer 2] [● Handled 5] │  LaneFilter
│ ▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇▇░░░░░░░░░░░ 55 / 120 min                                  │  BudgetBar
│ 🔎 Filter by title, author or file…                                   Sort: Attention ▾│
├──────────────────────────────────────────────────────────────────────────────────┤
│ ● #418 Support !include in YAML sources                 Needs your eye   ~20 min │  QueueRow
│   kai-n · first contribution · touches loaders/yaml.py                            │
│   "Mira has flagged unsafe include paths 6 times" · 2 findings · Fix ready ✓      │
│ ● #421 Add tomli-w for writing                        Needs another reviewer      │
│   new dependency · touches packaging · Suggest: Theo (security)   [Hand to Theo]  │
│ ● #415 Fix typo in docs                                          Handled for you │
│ …                                                                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

At ≥ 90rem, selecting a row (click or ↑/↓) shows a **PreviewPane** on the right: the PR summary, findings by lane (titles only), and **Open pull request** (Enter). At < 90rem, a click opens the PR directly.

## 2. Components

| Component | Data | Behaviour |
|---|---|---|
| `AnswerHeader` | `summary` from `GET /queue` | The sentence is composed from copy templates with counts (`copy/en.json` `queue.answer.*`). Plural rules use `Intl.PluralRules`. Zero-need state: "Nothing needs you today. Keeper handled all {n}." |
| Refresh button | `useConfirmableAction(POST /queue/refresh)` | Shows the estimate inline when known (`GET /status` gives per-PR averages); disabled in no-key mode (tooltip) |
| `LaneFilter` | `summary.by_lane` | A segmented control (radio group) with lane colour dots and counts; updates `?lane=` |
| `BudgetBar` | `attention_minutes_total`, `budget_minutes` | Stacked by lane colour; over budget shows a warning colour and "15 min over: consider handing off #421" (picks the unknown row with the largest attention) |
| Search | client-side filter over the loaded rows (title, author, file paths) | `/` focuses it |
| Sort | `attention` (default), `updated`, `number` | |
| `QueueRow` | `QueueRow` | Lane dot + label; title; meta (author, first-time tag, touched area); **reason line**: the top reason in plain words with a quote from the evidence where available; counts; fix status chip; hand-off chip with **Hand to {name}** (the hand-off action) on unknown rows. Hover or focus prefetches the PR queries. |
| `LaneGroupHeader` | when sort = attention | Groups rows under sticky lane headers with a one-line lane explanation |
| `QueueDigest` | `GET /queue/digest` | A collapsible "This week in plain words" card at the bottom; "Ask about this queue" opens Ask with the queue context |

## 3. States

| State | Display |
|---|---|
| Loading | `AnswerHeader` skeleton plus 6 row skeletons |
| Saved results | `ModeBadge` in the top bar; each row's lane chip has a tiny "saved" clock icon with a tooltip giving the date |
| Refresh running | The button shows a spinner with "Analysing 3 of 12…"; rows update as `analysis.updated` events arrive (a subtle highlight flash; none under reduced motion) |
| No open PRs | "No open pull requests in {repo}." + "Import another repository" (Settings) |
| No lens yet (imported project) | Rows show the lane "Not sorted yet" with the explanation "Keeper needs to learn {maintainer}'s lens first" and **Build lens** (a job) |
| Error | An inline error card with retry; the existing rows stay |

## 4. Accessibility

Rows are a list (`role="list"`), with each row a link whose accessible name is "PR 418, Support !include in YAML sources, needs your eye, about 20 minutes". The lane filter is a radio group. ↑/↓ move the selection when the list has focus; Enter opens.

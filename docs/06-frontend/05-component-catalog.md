# Component catalog

Shared components live in `frontend/src/components/` (primitives in `ui/`, domain components in `keeper/`). Screen-only components live with their screen in `frontend/src/screens/<screen>/`. Each shared component has a Vitest test and, where visual, a Playwright component screenshot at two container widths.

## 1. Primitives (`components/ui/`, wrapping Radix where noted)

| Component | Props (key) | Notes |
|---|---|---|
| `Button` | `variant: primary|secondary|ghost|danger`, `size: sm|md`, `loading`, `icon`, `kbd?` | Primary at most once per view (a lint-like test counts `variant="primary"` per screen) |
| `IconButton` | `label` (required, becomes `aria-label`), `icon` | |
| `Badge`, `Pill` | `tone`, `icon?` | |
| `Tooltip` (Radix) | `content`, `side` | 300 ms delay; also on focus |
| `Popover`, `DropdownMenu`, `Dialog`, `Sheet` (Radix Dialog as a side or bottom sheet), `Tabs`, `ToggleGroup`, `ScrollArea`, `Toast` | — | |
| `Skeleton` | `shape`, `lines` | Respects reduced motion |
| `Kbd` | `keys` | |
| `Markdown` | `source`, `components?` | `react-markdown` + GFM + sanitise; code blocks via `CodeBlock`; links open in a new tab with `noopener` |
| `CodeBlock` | `code`, `lang`, `copy` | Lazy shiki |
| `SplitPane` | `id` (persisted), `defaultSizes`, `minSizes` (percent) | `react-resizable-panels`; keyboard-resizable |
| `Term` | `term` | Dotted underline + tooltip from the glossary |
| `RelativeTime` | `at`, `demo?` | |
| `Money`, `Duration`, `Percent`, `Interval` | — | `Intl` formatting |

## 2. Keeper domain components (`components/keeper/`)

| Component | Props | Behaviour |
|---|---|---|
| `LaneBadge` | `lane`, `size`, `showLabel` | Icon + label + colour from tokens; tooltip with the lane meaning |
| `LaneDot` | `lane` | For dense lists; always paired with text nearby |
| `LaneFilter` | `counts`, `value`, `onChange` | A radio group |
| `AnswerHeader` | `title`, `subtitle?`, `actions?` | The page `h1` and the answer sentence |
| `BudgetBar` | `byLane`, `budget` | Stacked bar with labels |
| `QueueRow` | `row`, `selected`, `onOpen` | Container-query layout |
| `ReasonLine` | `reasons` | The top reason; "+2 more" popover |
| `SignalChips` | `signals` | |
| `FindingCard` | `finding`, `variant: pane|inline|compare|practice-reveal`, `onFeedback` | Includes `FeedbackActions` |
| `FeedbackActions` | `finding`, `canFix` | Accept, Edit, Dismiss (with reason menu), Good catch, Fix and test; Undo |
| `EvidenceList` | `pastComments`, `lensItems` | Quotes with links |
| `DiffView` | `files`, `findings?`, `mode: review|practice`, `onLineClick?`, `wrap`, `split` | `parse-diff`; virtualised for > 1,000 lines (`@tanstack/react-virtual`); inline slots for cards and notes |
| `CompareView` | `baseline`, `lens`, `pairs`, `human?` | SVG connectors recomputed with `ResizeObserver` |
| `FixTimeline` | `jobId` or a saved `fixRun` | Renders events; branch columns at ≥ container `md`, stacked below |
| `HandoffCard` | `handoff` | |
| `ReviewDraftPanel` | `draft`, `onChange` | Autosave |
| `JobProgress` | `jobId`, `compact?` | Step label, progress, cost, cancel |
| `ConfirmCostDialog` | `estimate`, `action`, `onConfirm` | Opened by `useConfirmableAction` |
| `ModeBadge` | `status` | |
| `RolePicker` | `people`, `value` | |
| `PersonAvatar` | `person`, `size` | The generated SVG |
| `LensItemCard`, `LensItemChip` | `item` | |
| `SupportMeter` | `support`, `precision`, `ci` | "seen in 9 · right 82% (65–93%)" |
| `HealthBadge` | `state` | |
| `EdgeTopList`, `EdgeMap` | `cells` | Grid heatmap with accessible cells |
| `LensDiffView` | `diff` | |
| `GrowthTrend` | `snapshots` | CSS bars |
| `MetricBar`, `CompareBars` | `value`, `ci`, `target?`, `label` | |
| `FalsifierList`, `CriteriaList` | `items` | |
| `ChatThread`, `ChatMessage`, `ChatInput`, `ToolSteps`, `ActionCard`, `CitationChip` | — | See [Ask](screens/03-ask.md) |
| `AskDrawer` | `context` | |
| `EmptyState`, `InlineError`, `PageError`, `KeyRequired` | — | See [States](screens/08-first-run-and-states.md) |
| `TourOverlay` | `steps` | Spotlight using `data-tour` targets |

## 3. Rules

- Components get data via props. Only screen containers call hooks that fetch data (`screens/*/index.tsx`).
- No component contains user-facing literals; strings come from `copy/en.json` via `t("key", vars)`. A test fails on JSX text literals outside `copy`.
- No component contains example data values (demo names, PR numbers). The hardcode guard covers `frontend/src` too.
- Every interactive element is keyboard-reachable with a visible focus ring (`--focus`).

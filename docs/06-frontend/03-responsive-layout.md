# Responsive layout

**Rule:** no fixed pixel widths or heights for layout, and no assumed resolution. Layout is driven by available space: fluid tokens, `minmax()` grids, `clamp()`, and **container queries** (components adapt to the space they are given, not to the window).

## 1. Techniques

| Technique | Where |
|---|---|
| `rem` for everything; `clamp()` for type and gutters | Global |
| CSS grid with `minmax(min(100%, 20rem), 1fr)` and `auto-fit` | Card grids (Lens items, Proof falsifiers) |
| Container queries (`@container`, Tailwind `@container` and `@md:` variants) | Queue rows, PR panes, finding cards, the chat column |
| `max-inline-size` measures: `--measure: 72ch` for prose, `--measure-chat: 46rem` for the chat column | Reading comfort on wide monitors |
| `dvh` units for full-height panes (`100dvh` minus the top bar) | Shell, PR split, chat |
| Resizable split panes (`react-resizable-panels`), sizes in percentages, persisted per screen in local storage | PR view (Diff + Findings), Ask (threads + chat), Proof (cases + detail) |
| `overflow-wrap: anywhere` for long identifiers; horizontal scroll only inside code | Diffs, paths |

## 2. Container sizes (component level)

| Container name | `sm` | `md` | `lg` | `xl` |
|---|---|---|---|---|
| Container widths | ≥ 24rem | ≥ 40rem | ≥ 56rem | ≥ 80rem |

## 3. Layouts per available width (viewport level)

| Viewport | Shell | Queue | Pull request | Ask | Lens | Proof |
|---|---|---|---|---|---|---|
| < 40rem (phones; best effort) | Bottom tab bar | Stacked cards | Tabs: Findings, Diff, Draft | Full width, threads in a sheet | Tabs stacked | Stacked |
| 40–64rem (tablets, small windows) | Top bar plus a nav sheet | One-column rows with a wrapping meta line | Findings above the diff, the diff collapsible | Threads in a sheet | One column | One column |
| 64–90rem (laptops: 1280, 1366, 1440) | Left rail (icons plus labels; auto-collapses to icons below 72rem) | Rows with inline lane chips and a right-aligned meta column | **Split**: findings (≈ 38%) and diff (≈ 62%) | Threads rail (16rem) + chat (centred, `--measure-chat`) | Two columns (card + items) | Cases list + detail |
| 90–120rem (1536, 1920 monitors) | Rail | Rows + an optional preview pane (opening a row shows the PR summary on the right; Enter opens the full PR) | Split + a right drawer for Ask without squeezing the diff below 50% | Threads + chat + the context panel (cards from the conversation) | Three columns | Three columns |
| > 120rem (2560, 3440 ultrawide) | Rail | Content max width `110rem`, centred; the preview pane is always visible | Max width `140rem`; three panes (findings, diff, draft) | Chat column stays at `--measure-chat`; side panels widen | Max width `130rem` | Max width `130rem` |

These are expressed as container queries on the main content area, which also accounts for the rail's width.

## 4. Behaviour details

- **Diff lines** never wrap code by default (a toggle enables wrapping; the preference is persisted). Line numbers are sticky. Inline finding cards span the diff width.
- **Tables** (usage, cases) become stacked cards below the container `md`.
- **Dialogs** are `min(36rem, 100vw − 2·gutter)` wide; on phones they become bottom sheets.
- **The Ask drawer** is `clamp(22rem, 30vw, 34rem)` wide; below `lg` it is a full-screen sheet.
- **Zoom:** works at 200% browser zoom without loss of content (WCAG 1.4.4/1.4.10). At 400% (equivalent to 320 CSS px), it reflows to the phone layout.

## 5. Test matrix

Playwright runs the core flows (the tour, Queue → PR → Compare → Fix, Ask, Lens tabs, Proof, Practice taste) and screenshot checks at:

| Viewport (CSS px) | Device class | DPR |
|---|---|---|
| 1280×720 | small laptop | 1 and 2 |
| 1366×768 | common laptop | 1 |
| 1440×900 | MacBook Air | 2 |
| 1536×864 | Windows laptop at 125% scaling | 1.25 |
| 1920×1080 | monitor | 1 |
| 2560×1440 | QHD monitor | 1 |
| 3440×1440 | ultrawide | 1 |
| 1024×768, 768×1024 | tablet | 2 |
| 390×844 | phone | 3 |

Assertions: no horizontal page scroll (`document.documentElement.scrollWidth <= innerWidth`); the primary action is visible without scrolling on every screen from 1280×720 up; no text is clipped (an axe check plus a custom overflow probe); and the screenshots are reviewed.

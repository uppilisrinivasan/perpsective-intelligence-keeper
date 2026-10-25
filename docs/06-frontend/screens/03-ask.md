# Screen: Ask

**Question answered:** anything, in the user's words. **Primary action:** type a question. **Requirements:** FR-ASK. Backend: [Assistant](../../04-architecture/06-assistant.md).

## 1. Layout

```
┌ Threads (16rem) ───────┬──────────────────────── Chat (max 46rem, centred) ─────────────────────┐
│ [+ New chat]           │                                                                        │
│ Today                  │   (empty thread)                                                       │
│  Why #421 needs Theo   │        Ask Keeper about the queue, a PR, the lens or the proof.        │
│  Lens changes v1→v2    │   ┌───────────────────────────┐ ┌──────────────────────────────┐       │
│ Earlier                │   │ What needs me today?      │ │ What would Mira notice in #418? │     │
│  …                     │   └───────────────────────────┘ └──────────────────────────────┘       │
│                        │   ┌───────────────────────────┐ ┌──────────────────────────────┐       │
│                        │   │ What does the lens miss?  │ │ Is the lens proven?           │      │
│                        │   └───────────────────────────┘ └──────────────────────────────┘       │
│                        │                                                                        │
│                        │ ┌────────────────────────────────────────────────────────────────────┐ │
│                        │ │ Ask anything…                         [📎 PR #418 ×]          [↑]  │ │
│                        │ └────────────────────────────────────────────────────────────────────┘ │
│                        │ Answers come from Keeper's data. Nemotron 3 Super · about $0.01 each    │
└────────────────────────┴────────────────────────────────────────────────────────────────────────┘
```

At ≥ 90rem a right **context panel** lists every card mentioned in the thread (PRs, findings, lens items) for quick navigation.

## 2. Message rendering

| Element | Rendering |
|---|---|
| User message | A right-aligned bubble (surface-2), plain text, with context chips |
| Assistant message | Left-aligned, no bubble (full-width prose like ChatGPT and Claude), markdown (sanitised), code blocks with copy |
| Tool steps | Above the answer, collapsed into one line while running ("Looking at PR #418 · Reading Mira's past comments…" with a spinner) and after completion ("Used 3 sources ▸"), expandable into a step list with durations |
| Streaming | Text appears as it arrives; a blinking caret (none under reduced motion); **Stop** replaces Send |
| Citation markers | Inline chips (`PullChip`, `FindingChip`, `LensItemChip`), colour-coded by lane, clickable, with a hover card preview |
| Action cards | `ActionCard`: the title ("Fix and test 1 finding on #418"), what will happen, the estimate, **Confirm** (primary) and **Cancel**; after confirming, it turns into a live `JobProgress` with a link to the full view |
| Metric cards | Inline `MetricStat` with the interval |
| Footer per answer | Copy, a model and cost tooltip, Retry |
| Errors | An inline error line with Retry; `spend_cap_reached` shows the cap banner text |

## 3. Input

- An auto-growing textarea (1–8 lines), Enter sends and Shift+Enter adds a newline, `/` focuses from anywhere on the page.
- **Context chips:** the context attached from the drawer origin, removable. **@** opens a picker to attach a PR, lens item or Proof run (typeahead over `GET /queue` and lens items).
- Suggested prompts (from `GET /chat/suggestions`) appear on empty threads and as up to 3 follow-up chips after each answer (`suggestions` returned in `chat.done`, optional).

## 4. Threads

New, rename (inline), delete (with confirm), grouped by Today, Previous 7 days and Earlier. The title is generated after the first answer (`assistant_title`). Threads opened from a drawer show their context icon.

## 5. Drawer variant

`AskDrawer` (from any screen): the same chat component with no threads rail; the header shows "Ask about PR #418" and **Open in Ask** (moves to `/ask/:threadId`). It keeps state while navigating within the same context.

## 6. No-key mode

The input is disabled with "Add a Nemotron API key to ask your own questions" (link to how). Saved example threads are listed under "Saved examples" and open read-only, with cards that work.

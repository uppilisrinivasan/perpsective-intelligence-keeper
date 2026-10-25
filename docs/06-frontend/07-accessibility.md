# Accessibility

Target: **WCAG 2.2 AA** (NFR-A11Y).

| Area | Requirement |
|---|---|
| Structure | One `h1` per page (the `AnswerHeader`); landmarks (`header`, `nav`, `main`, `aside`); a skip link |
| Keyboard | Everything operable by keyboard; logical order; no traps (dialogs trap focus and restore it on close); shortcuts can be disabled in Preferences |
| Focus | A visible 2 px ring in `--focus` with ≥ 3:1 contrast; never removed |
| Colour | Never the only cue: lanes have icons and labels; heatmap cells have text and patterns; pass and fail have icons |
| Contrast | Text ≥ 4.5:1, UI ≥ 3:1, in both themes (a token test computes it) |
| Motion | `prefers-reduced-motion` honoured; no auto-playing animation; the tour's spotlight transition is instant when reduced |
| Live regions | Job progress announces step changes (polite); chat streaming announces when complete ("Answer ready"), not per token; toasts are polite; errors are assertive |
| Diffs | Lines are a table with row headers (line numbers); added and removed lines announced ("added line 44"); inline findings are `aside` with a label |
| Compare connectors | Decorative (`aria-hidden`); the pairing is also given in text ("Matches: …") |
| Forms | Labels for every input; errors linked with `aria-describedby` |
| Target size | ≥ 24×24 CSS px (WCAG 2.5.8); 44×44 on touch layouts |
| Zoom and reflow | 200% without loss; reflow at 320 CSS px |
| Language | `lang="en"`; copy at a plain reading level |

**Tests:** `@axe-core/playwright` on every screen in the viewport matrix (zero serious or critical violations); keyboard-only Playwright runs of the tour and the Queue → PR → Fix flow; Vitest checks with Testing Library queries by role (which also guards accessible names).

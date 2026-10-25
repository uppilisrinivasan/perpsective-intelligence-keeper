# Design system

All values are **tokens**: CSS custom properties in `frontend/src/styles/tokens.css`, mapped into Tailwind v4 via `@theme`. Components never use raw hex values, pixel font sizes or arbitrary spacing. A lint rule (`stylelint` plus a custom ESLint rule that bans `[#…]` and `px` in class strings, except `1px` borders) enforces this.

## 1. Colour

Both themes are defined. The theme follows `prefers-color-scheme` by default and is switchable in Settings (`system`, `light` or `dark`). Contrast: text ≥ 4.5:1, large text and UI ≥ 3:1, checked by a token test.

### 1.1 Neutrals and surfaces

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `oklch(0.985 0.003 250)` | `oklch(0.17 0.01 250)` | Page |
| `--surface` | `oklch(1 0 0)` | `oklch(0.21 0.012 250)` | Cards, panels |
| `--surface-2` | `oklch(0.965 0.004 250)` | `oklch(0.25 0.012 250)` | Inset areas, code |
| `--border` | `oklch(0.9 0.005 250)` | `oklch(0.32 0.012 250)` | Dividers |
| `--text` | `oklch(0.22 0.02 250)` | `oklch(0.95 0.005 250)` | Body |
| `--text-muted` | `oklch(0.48 0.02 250)` | `oklch(0.72 0.01 250)` | Secondary |
| `--focus` | `oklch(0.6 0.18 255)` | `oklch(0.72 0.15 255)` | Focus ring |

### 1.2 The lane language (the core of the visual identity)

| Lane | Token family | Hue (OKLCH) | Icon (lucide) | Label | Meaning shown in its tooltip |
|---|---|---|---|---|---|
| edge | `--lane-edge-{bg,fg,border,solid}` | orange, h≈55 | `eye` | Needs your eye | Something the maintainer would notice that a generic AI reviewer would not |
| blind_spot | `--lane-blind-…` | blue, h≈250 | `scan-search` | Worth a second look | Something the model catches that the maintainer has tended to miss |
| shared | `--lane-shared-…` | grey-green, h≈160, low chroma | `check-circle-2` | Handled for you | Both the maintainer and the model would catch this, so Keeper can handle it |
| unknown | `--lane-unknown-…` | violet, h≈300 | `user-round-search` | Needs another reviewer | Outside what the lens knows (new territory or a risk signal), so Keeper hands it off |
| baseline_only | `--lane-baseline-…` | neutral | `list` | Other model notes | Collapsed |

Each family: `bg` (tinted background, ≈ 0.96 L light / 0.28 L dark), `fg` (text on bg, ≥ 4.5:1), `border`, `solid` (the bar or dot colour, ≥ 3:1 against the surface).

### 1.3 Semantic

`--success`, `--warning`, `--danger`, `--info`, each with `bg` and `fg`. These are used for tests passing or failing, cost warnings and errors. They are distinct from the lane hues: success is green h≈145 (more saturated than shared), and danger is red h≈25 (separated from edge orange by both hue and lightness, and always paired with an icon).

### 1.4 People

Avatars are generated (`/avatars/{id}.svg`) with a hue from a hash of the person ID, avoiding the four lane hues ±20°.

## 2. Typography

Fluid sizes use `clamp()`, so text scales between a 1280 px laptop and a 2560 px monitor without breakpoints.

| Token | Value | Use |
|---|---|---|
| `--font-sans` | `"Inter Variable", system-ui, sans-serif` | UI |
| `--font-mono` | `"JetBrains Mono Variable", ui-monospace, monospace` | Code, diffs |
| `--text-xs` | `clamp(0.75rem, 0.72rem + 0.1vw, 0.8125rem)` | Meta |
| `--text-sm` | `clamp(0.8125rem, 0.78rem + 0.12vw, 0.875rem)` | Secondary, table |
| `--text-base` | `clamp(0.9375rem, 0.9rem + 0.15vw, 1rem)` | Body |
| `--text-lg` | `clamp(1.0625rem, 1rem + 0.25vw, 1.1875rem)` | Card titles |
| `--text-xl` | `clamp(1.25rem, 1.15rem + 0.4vw, 1.5rem)` | Section titles |
| `--text-2xl` | `clamp(1.5rem, 1.3rem + 0.8vw, 2rem)` | Answer headers |
| `--text-code` | `clamp(0.8125rem, 0.79rem + 0.1vw, 0.875rem)` | Diff lines |
| Line heights | 1.5 body, 1.25 headings, 1.6 code | |
| Weights | 400, 500 (labels), 600 (headings) | |

Users' browser font-size settings are respected (rem everywhere).

## 3. Space, radius, elevation, motion

- **Space scale** (rem): `--space-1` 0.25, `2` 0.5, `3` 0.75, `4` 1, `5` 1.25, `6` 1.5, `8` 2, `10` 2.5, `12` 3, `16` 4. Page gutters: `--gutter: clamp(1rem, 0.5rem + 1.5vw, 2.5rem)`.
- **Radius:** `--radius-sm` 0.375rem, `--radius` 0.625rem, `--radius-lg` 0.875rem, `--radius-full`.
- **Elevation:** `--shadow-1` (cards), `--shadow-2` (popovers), `--shadow-3` (dialogs). In dark mode, borders replace most shadows.
- **Motion:** `--dur-fast` 120 ms, `--dur` 200 ms, `--dur-slow` 320 ms; `--ease` `cubic-bezier(0.2, 0, 0, 1)`. All motion is disabled under `prefers-reduced-motion: reduce` (instant state changes; the streaming text still appears, without a caret blink).

## 4. Data display

- **Bars, not charts.** Metrics use CSS bars (`MetricBar`, `CompareBars`): a value bar, an interval whisker, and a target tick. The edge map is a CSS grid heatmap (`EdgeMap`). There is no chart library.
- **Numbers:** tabular figures (`font-variant-numeric: tabular-nums`). Formatting uses `Intl.NumberFormat` (locale from the browser). Durations are humanised ("about 55 min"). Money: `$0.03`, or `< $0.01`.
- **Dates:** relative within 7 days ("2 days ago", with the exact date in the tooltip). In demo mode, relative to `demo_now`, labelled "in the demo world" in the tooltip.

## 5. Iconography and imagery

lucide icons at 1em (they scale with text), stroke 1.75. There are no illustrations except the empty-state glyph composition (lane icons in a circle). There is no stock imagery.

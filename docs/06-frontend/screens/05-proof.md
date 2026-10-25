# Screen: Proof

**Question answered:** "Does Keeper notice like the maintainer on pull requests it never saw?" **Primary action:** read the verdict, then **Open a case**. **Run again** is confirmable. **Requirements:** FR-FID. Method: [Fidelity Test](../../02-methodology/11-fidelity-test.md).

## 1. Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ ✓ Keeper sees like Mira on 38 PRs it never saw                       lens v1 · Saved run ▾   │  VerdictHeader
│ It caught {k_recall}% of what Mira raised; generic review caught {b_recall}%.                 │
│ Of what Mira raised that generic review missed, the lens recovered {residual_recall}%.        │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ What Mira raised, caught by…                                                                  │  CompareBars
│  Keeper (lens + handled) ████████████████████▌ 64%  (55–72)                                  │
│  Lens alone              ████████████████▌     52%  (43–61)                                  │
│  Generic review          ██████████▌           33%  (25–41)                                  │
│ Difference Keeper − generic: +31 points (22–40) ✓ above zero                                  │
│ Noise per PR   Keeper 0.9 · generic 1.2  ✓      No exaggeration: max ratio 1.12 ≤ 1.3 ✓      │  CriteriaList
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Ways this could have been wrong                                                               │  FalsifierList
│  ✓ The residual predicts something      ✓ The lens beats generic review on unseen PRs         │
│  ✓ No exaggeration of Mira's favourite concerns   ✓ Mira's own edge is holding                │
│  ✓ Practice doesn't make learners worse unassisted  ✓ Edge growing without losing accuracy   │
│  – Perspective is just preference (not tested in this version)                                │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ Cases (38)  [Search] [Lens caught it | Lens missed it | Extra findings]                        │  CaseList
│ #301 Add env interpolation   Mira 3 · Keeper ●●○ · generic ●○○                                │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

All numbers in this sketch are illustrative. Every number on the screen comes from the selected run.

## 2. Components

| Component | Content |
|---|---|
| `VerdictHeader` | Pass or fail icon and the sentence from §4 of the methodology ("Keeper sees like Mira on PRs it never saw" / "Not yet: Keeper doesn't beat generic review here"), filled from the run's metrics via copy templates |
| `CompareBars` | Substantive recall for Keeper, Lens and Baseline, with 95% bootstrap whiskers; then the paired difference with its interval. Tooltip: "Of everything Mira raised on these PRs, the share this system also raised." The label for the baseline is "Generic review (same model, no lens)". |
| `ResidualStat` | Residual recall of Lens and Keeper, with the explanation "generic review is 0 here by definition" |
| `CriteriaList` | One line per pass criterion (recall difference > 0, noise ratio, caricature ratio and JSD, unknown-lane recall in the demo), each pass or fail with the numbers; a fail is never hidden |
| `FalsifierList` | Each falsifier as a plain question with its result, pass, fail or "not tested in this version" with the reason; expandable numbers |
| `SensitivityNote` | Collapsible: recall with line windows 3 and 10, partial matches as 0 and as 1 |
| `HowThisWorks` | A collapsible 4-step diagram (held-out PRs → generic review, lens, Keeper → matched to what Mira actually wrote → compared), and "Ask: explain the Fidelity Test" |
| `CaseList` | Per PR: title, the count of Mira's findings, and dots per system (filled = caught); filters; virtualised |
| `CaseDetail` | The PR Compare view with the third column "What Mira actually wrote" |
| `RunPicker` | Past runs (lens version, date, origin, pass) |
| Run again | Confirmable, with the estimate and duration, and a "Use Batch (cheaper, slower)" checkbox when `BATCH_API_ENABLED` |

## 3. States

- No run: "No proof yet." + **Run the Fidelity Test** (with the estimate and duration), or in no-key mode "Not in the saved results".
- Running: progress by case (`fidelity.case`); for batch, "Waiting for Token Factory batch (12/40)".
- Failed criteria: the header uses the warning style with the failed criteria named, plus a link to Lens → items filtered to low precision.
- Imported repository: the header names the repository and the maintainer with attribution; the demo-only criteria are omitted.

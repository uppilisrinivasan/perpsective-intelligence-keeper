# The Growth Test and health states

> "Helping you is easy. Leaving you better is the test." (IP §7)

Two kinds of growth are measured: a **learner** growing toward a maintainer's lens (Practice), and the **maintainer** staying ahead of their own lens (the growth residual G).

## Part A · Practice: the learner's Growth Test

### A1. The item bank

An item is a held-out PR for the target person P (the maintainer) with:
- ≥ `practice.min_findings` (2) substantive findings by P;
- a diff of ≤ `practice.max_changed_lines` (250);
- no use in the tour's aha step.

Each item gets a **difficulty** by code: `d = Σ over P's findings (1 if the baseline also found it, else 2) × severity weight`, bucketed into easy, medium and hard by tertiles. Each also gets a **category profile** (the categories of P's findings).

### A2. Parallel forms (FR-GROW-5)

A session of kind `before`, `learn` or `after` has `k` items (`practice.k`, 5 for before and after, 5 for learn). For each learner, forms are drawn **without replacement across that learner's sessions**:
1. Stratify by difficulty bucket: aim for 2 medium, 2 hard and 1 easy (configurable).
2. Within each stratum, choose greedily to minimise the L1 distance between the form's category profile and P's overall profile.
3. The before and after forms are built together to minimise the difference of their mean difficulty and their profile distance (`test_parallel_forms_balanced` requires a mean-difficulty difference ≤ 0.25 and an L1 profile distance ≤ 0.3).
4. Learn items preferentially come from the edge map's top cells.

The judge-as-learner path ("Try it yourself" in the tour) uses one easy-to-medium item, labelled "1-PR taste test (not a Growth Test)".

### A3. Sessions

| Kind | What the learner sees | What is hidden |
|---|---|---|
| `before` | The PR title, description and diff. A note box per line (click the gutter) and a PR-level note box. | All Keeper output, P's comments, lens items |
| `learn` | Step 1: the same as before. Step 2: after submitting, one **coaching hint** per missed costly finding (the `practice_coach` prompt: points to *where* and *what kind of thing* to look for, never the answer: "Look at how `resolve()` handles `..` coming from the file."). Step 3: a second try. Step 4: the **reveal**: P's comments (attributed), the matching lens item and its rationale, and which of the learner's notes matched. | Before step 4: P's comments and the lens |
| `after` | The same as before, on a parallel form | The same as before |

Rules from IP §6.5: *keep difficulty where the lens is forming* (the learner always tries first), *test without the tool* (before and after are unassisted), *do not flatter* (the result states the misses plainly).

### A4. Scoring (`practice_score`, `judge` model)

For each item: match the learner's notes (as findings with `source = learner`) against P's substantive findings with the [matching algorithm](04-matching-and-residual.md), plus the `practice_score` prompt's feedback line per note. Then compute:

| Measure | Definition |
|---|---|
| `recall` | matched weight ÷ the number of P's substantive findings |
| `costly_recall` | the same, weighted by the cost weight w(I) of the lens item each of P's findings belongs to (default 1 if none) |
| `costly_misses` | P's findings with w ≥ `practice.costly_threshold` (0.5) that were not matched |
| `own_eye` | learner notes unmatched to P but matched to a baseline finding with a linked bad outcome, or to a ground-truth slot (demo). These are valid catches P did not make. They are credited, never penalised. |
| `noise` | learner notes matched to nothing, with the judge's verdict `not_an_issue` |

Session result = sums over items. **Growth** = after − before for `recall`, `costly_recall` and `costly_misses`, with a note that n = k items per form and that the difference is indicative only. If `own_eye` falls between before and after while `recall` rises, the UI notes "You're catching more of what Mira catches. Keep your own eye too: you found fewer things she didn't." (protecting against the "absorbed" failure).

### A5. Learner lens diff

After ≥ 2 sessions, Keeper shows the learner's **lens diff**: the categories and lens items they now catch that they missed before ("Started catching: include-path escapes"), and the ones still missed.

## Part B · The maintainer's growth residual and health

### B1. The growth residual

For lens version v_k (cutoff T_k) and the PRs P reviewed after T_k (the next period):
- L(S) = the lens findings of v_k on S;
- **G(S) = H(S) − L(S)** (by matching): what P noticed that P's own earlier lens did not predict;
- `G_rate` = substantive |G| per PR, and `G_novel` = the G findings also unmatched by C (new edge, not merely something generic).

### B2. Period measures

For consecutive periods (`growth.period_months`, 3) over the history, computed with the lens version current at each period's start:

| Measure | Definition |
|---|---|
| `r_plus_rate` | P's substantive R+ per reviewed PR |
| `r_plus_hit` | the share of P's R+ findings on merged PRs that were addressed **or**, when ignored, were followed by a linked bad outcome; a proxy for "validated R+" |
| `costly_r_minus_rate` | R− findings matching blind-spot items per PR |
| `g_rate` | as in B1 |
| `assisted_share` | the share of P's findings that were accepted Keeper suggestions (only after Keeper is in use; 0 in historical data) |
| `unassisted_recall` | P's recall in an unassisted Practice check (optional; the maintainer can take one) |

### B3. Health states (FR-GROW-9; `config/growth.yaml`)

The rules are evaluated on the last two periods (trend = the last minus the previous, with a deadband `growth.deadband` of 0.1 relative change):

| State | Rule | Plain explanation shown |
|---|---|---|
| `insufficient_data` | < `growth.min_prs_per_period` (8) reviewed PRs in either period | "Not enough recent reviews to tell" |
| `replaced` | `g_rate` ≤ `growth.g_floor` (0.05) for 2 periods | "Your lens now predicts nearly everything you notice. Keeper may be doing your noticing; try reviewing a few PRs without it." |
| `absorbed` | `r_plus_rate` falling **and** `costly_r_minus_rate` falling **and** P's findings increasingly match C | "You're noticing more like generic review: fewer blind spots, but less of your own edge" |
| `self_caricature` | `r_plus_rate` rising **and** `r_plus_hit` falling | "You're flagging more unusual things, but fewer of them turn out to matter" |
| `deskilling` | `assisted_share` rising **and** `unassisted_recall` falling (only if both are available) | "With Keeper you catch more; without it, less" |
| `healthy` | otherwise, if `costly_r_minus_rate` is not rising and `r_plus_rate` is not falling | "Fewer costly blind spots, your edge intact, and you're still noticing new things" |

Evaluation order: insufficient_data → replaced → deskilling → self_caricature → absorbed → healthy (the first match wins).

### B4. The planted drift in the demo

The scenario plants a concern the maintainer starts raising in the last 6 months (for example "type hints on public functions"). Lens v1 (the earlier cutoff) cannot predict it, so it appears in G for the held-out period. v2 (built including that period) captures it as a new item; the v1 → v2 lens diff shows "Started noticing". `test_growth_residual_on_drift_slot` checks both.

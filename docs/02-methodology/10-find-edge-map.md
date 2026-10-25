# Find: where the maintainer's eye matters most (the edge map)

> "Find looks for perspective–problem fit: situations where a person's validated residual is large, where a consensus miss is costly, and where reality answers quickly enough for the loop to turn." (IP §6.1)

## 1. Cells

An edge-map cell is (area, category):
- **area** = a path prefix at depth `find.area_depth` (2, for example `strata/include`), computed from the changed files of training PRs. Files at the root are grouped as `(root)`. Tests map to the area they test: a test file `tests/test_include*.py` maps to the area whose module stem matches, otherwise to `tests`.
- **category** = the taxonomy category (substantive only).

## 2. Measures per cell, for person P, lens version v, ruler

| Measure | Definition |
|---|---|
| `volume` | PRs per month touching the area (last 12 months before the cutoff) |
| `residual_rate` | P's R+ findings in the cell per reviewed PR touching the area |
| `shared_rate` | P's shared findings in the cell per reviewed PR touching the area |
| `cost` | Σ over linked bad outcomes in the cell of the severity weight, ÷ PRs touching the area. Bad outcomes include those after merges where P's concern was absent or ignored. |
| `speed` | Median days from merge to the first linked bad outcome (lower is faster); `tests_present` = whether the area has tests (from the code index) |
| `value` | `residual_rate × (1 + cost_weight × cost) × log1p(volume) × speed_factor`, where `speed_factor = 1.2` if tests are present or the median speed is < 14 days, else 1.0. Weights are in `config/find.yaml`. |

## 3. Output

- **Top cells** (≤ 6) by value with ≥ `find.min_findings` (5) findings: "Where your eye matters most". Each shows the area, the category label, "You catch 3.4× more here than generic review" (`(residual_rate + shared_rate) / max(shared_rate, ε)`, capped and labelled), the bad outcomes with links, and the lens items involved.
- **Enough-cells** (≤ 4) where `shared_rate / (shared_rate + residual_rate) ≥ find.shared_dominant` (0.7): "Generic review is enough here". These are candidates for delegating fully to the shared lane.
- **Gaps:** areas with high volume and few findings by anyone: "Nobody looks closely here". They feed the `low_lens_coverage` risk signal.

## 4. Use elsewhere

- The attention estimate adds `edge_map_bonus = find.attention_bonus × normalised value` (0 to 3 minutes) for PRs touching top cells (FR-FIND-4).
- Practice chooses `learn` items preferentially from top cells (they are where a successor needs the eye most).

## 5. Validation (demo)

The scenario plants the maintainer's edge concerns in specific areas, with outcome consequences. `test_edge_map_ranks_planted_areas_first` requires that the planted high-value areas take ≥ 3 of the top 4 positions.

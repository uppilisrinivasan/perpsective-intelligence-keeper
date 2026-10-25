# Glossary

Each concept has **one** name in each layer. Code, database, API and UI MUST use the names in this table. When the UI name differs from the code name, the UI name is in the *UI* column. Concepts never shown to users have "(not shown)".

## Core concepts

| Concept | Code / DB / API | UI | Definition |
|---|---|---|---|
| Situation | `situation` (always a pull request in Keeper) | "pull request" or "PR" | The unit Keeper reasons about: one PR with its diff, description, files touched and metadata. |
| Finding | `finding` | "comment" (maintainer), "note" (Keeper) | One thing someone noticed in a situation: an anchor (file plus line range, or the whole PR), a concern category, a statement, a severity and a kind. See [Situations and findings](../02-methodology/01-situations-and-findings.md). |
| Finding source | `finding.source`: `human`, `baseline`, `lens`, `learner` | "Mira", "Generic review", "Keeper", "You" | Who or what produced the finding. `human` findings also carry `person_id`. |
| Substantive finding | `finding.substantive: bool` | (not shown) | A finding whose category is not `style` or `social`. Fidelity counts only substantive findings. |
| Human findings, H(S) | `H` | "what Mira noticed" | The set of substantive findings a person made on a situation. |
| Baseline findings, C(S) | `C` | "Generic review" | What the pinned generic reviewer (Nemotron plus static tools) notices. |
| Residual, R(S) | `residual` | "What Mira catches that generic review misses" | R = H − C, computed by matching (see below). |
| Positive residual, R+ | `r_plus` | "Your edge" | Findings in H with no match in C. |
| Negative residual, R− | `r_minus` | "Generic review also mentions" (uncalibrated), "Worth a second look" (calibrated) | Findings in C with no match in H. |
| Shared finding | `shared` | "Handled for you" | A finding in H matched by one in C. |
| Ruler | `ruler` | "Generic review (pinned)" | The exact baseline configuration: model ID, prompt ID and version hash, decoding parameters, static tools and their versions. A residual is only valid under one ruler. |
| Lens | `lens` | "Mira's lens", "your lens" | A person's learned way of seeing: a versioned set of lens items plus exemplars that predicts their residual on new PRs. |
| Lens version | `lens_version` (integer `version`, label `v1`, `v2`…) | "v1", "v2" | An immutable snapshot of a lens. |
| Lens item | `lens_item` | "what you notice" (a card) | One attention pattern: statement, rationale, triggers, exemplars, counter-examples and statistics. |
| Lens card | `lens_card` (markdown) | "Lens card" | The human-readable account of the lens, generated from its items. |
| Lens skill package | `lens_package` | "Export lens" | A portable archive (`lens.json`, `LENS.md`, `SKILL.md`) that other agents can run. |
| Lens diff | `lens_diff` | "What changed" | A changelog between two lens versions: items added, retired, reworded or re-weighted. |
| Exemplar | `exemplar` | "Your past review" (citation) | A past human finding cited as evidence for a lens item or a drafted comment. |
| Lane / case | `lane`: `shared`, `edge`, `blind_spot`, `unknown` | "Handled for you", "Needs your eye", "Worth a second look", "Needs another reviewer" | The four cases of *who teaches whom*. Assigned to each routed finding and to each PR. |
| Routed finding | `routed_finding` | a note in the PR view | A finding after routing: its lane, its sources (lens, baseline or both), its evidence and its suggested action. |
| Risk signal | `risk_signal` | "Why another reviewer" chip | A configured condition (build script, binary file, new dependency…) that forces at least the `unknown` lane unless a validated lens item covers it. |
| Another lens | `handoff` | "Hand to …" | Routing a PR to a different person whose lens is competent for its risk signals. |
| Lens distance | `lens_distance` (0 to 1) | "sees differently from you" | How differently two lenses see the same situations (see [Routing](../02-methodology/07-routing-and-triage.md) §5). |
| Attention estimate | `attention_minutes` | "≈ 6 min" | Estimated maintainer minutes a PR needs, given its lane and size. |
| Weekly attention budget | `attention_budget_minutes` | "Your review time this week" | The maintainer's stated time for review (default from config). |
| Triage | `triage` | "Queue" | Ranking open PRs by attention needed, with lane assignment. |
| AI-slop signal | `slop_score` | "Looks auto-generated" chip | The likelihood that a contribution is low-effort machine output. It is judged on content only, never on who the author is. |
| Review draft | `review_draft` | "Draft review" | A review composed from routed findings, labelled as Keeper's, editable, exportable. |
| Fix run | `fix_run` | "Fix" | One attempt by Keeper to implement the fix for one or more findings, with tests. |
| Fix attempt | `fix_attempt` | "Attempt 1, 2…" | One iteration: plan or repair, apply, test. |
| Branch | `fix_branch` | "Option A / B" | A parallel candidate fix started from the same sandbox checkpoint. |
| Sandbox | `sandbox` (`local`, `docker`, `contree`) | "Sandbox" | An isolated place where the project's tests run. |
| Outcome | `outcome`: `merged`, `closed_unmerged`, `reverted`, `post_merge_bug`, `follow_up_fix`, `ci_failed` | "What happened next" | Reality's answer about a PR. |
| Calibration | `calibration` | "Track record" | Per-lens-item statistics against outcomes: support, hit rate and a credible interval. |
| Item status | `lens_item.status`: `validated`, `candidate`, `bias_suspected`, `retired`, `disabled_by_owner` | "Proven", "Still learning", "Possible bias", "Retired", "Turned off" | Lifecycle state of a lens item. |
| Edge map | `edge_map` | "Where your eye matters most" | Areas (path prefixes × concern categories) ranked by residual size × cost × volume. |
| Fidelity run | `fidelity_run` | "Proof run" | One execution of the Perspective Fidelity Test. |
| Held-out set | `holdout` | "PRs Keeper never saw" | PRs after the lens's training cutoff. |
| Caricature ratio | `caricature_ratio` | "Exaggeration check" | For a person's top concern categories, the rate predicted by the lens ÷ the actual rate. |
| Practice session | `practice_session` (`kind`: `before`, `learn`, `after`) | "Practice" | A held-out review check or a learning session for a learner. |
| Learner | `learner` | "You" (in Practice) | A person practising review in someone's lens. |
| Growth residual, G(S) | `growth_residual` | "New since v1" | What a person notices now that their own earlier lens did not predict. |
| Health state | `health_state`: `healthy`, `absorbed`, `self_caricature`, `deskilling`, `replaced`, `insufficient_data` | "Healthy", "Becoming generic", "Exaggerating", "Leaning on Keeper", "Lens has caught up", "Not enough data yet" | The diagnosis of growth. See [Growth Test](../02-methodology/12-growth-test-and-health.md). |
| Consent | `consent` | "You've allowed Keeper to learn from…" | The maintainer's opt-in record for building a lens from their reviews. |
| Workspace | `project` | "Project" | One repository Keeper has data for (the demo project, or an imported one). |
| Demo clock | `demo_now` | "Today" (in demo mode) | The fixed "now" of the demo data, from `data/manifest.json`. All relative dates in demo mode use it. |
| Snapshot | `snapshot` | "Saved results" badge | Pre-computed analysis results committed in `data/snapshots/`, used when there is no API key. |
| Mode | `KEEPER_MODE`: `demo`, `workspace` | "Demo project" / "Your projects" | Whether the app opens the bundled demo or imported projects. |
| Job | `job` | progress toasts and panels | A long-running backend task with streamed progress. |
| Model role | `fast`, `judge`, `deep` | "Lightning", "Super", "Ultra" | Configured model tiers. The UI shows the model's display name from config. |
| LLM call record | `llm_call` | Settings → Usage | The audit row for each model call: role, model, tokens, cost, latency, prompt ID. |

## Words the UI does not use

The UI never says *residual*, *H(S)*, *C(S)*, *R−*, *salience*, *embedding* or *ruler*, except inside the expandable "How we measure this" panels on Proof and Lens. There it uses the papers' notation with a plain-language explanation next to it. See [Copy guide](../06-frontend/06-copy-guide.md).

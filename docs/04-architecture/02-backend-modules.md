# Backend modules

Package `keeper` in `backend/keeper/`. Dependencies point **downward** in this table. An import-linter contract (`backend/.importlinter`) enforces the layers and the special rules below.

| Layer | Package | Responsibility | May import |
|---|---|---|---|
| 6 API | `keeper.app` | FastAPI app factory, routers (`routers/*.py`), dependency injection, auth, error handlers, the SSE endpoints, static file serving | everything below |
| 5 Assistant | `keeper.assistant` | Chat loop, tool registry, confirmation cards | services (4) |
| 4 Services | `keeper.services` | Use-case functions called by routers and tools: `queue`, `pulls`, `fixes`, `lens`, `proof`, `practice`, `projects`, `settings`, `usage`, `tour` | pipelines (3) |
| 3 Pipelines | `keeper.ingest`, `keeper.findings`, `keeper.baseline`, `keeper.residual`, `keeper.lens` (`build`, `apply`, `card`, `diff`, `package`, `governance`), `keeper.route` (`lanes`, `risk`, `triage`, `handoff`), `keeper.review`, `keeper.fix`, `keeper.outcomes`, `keeper.calibrate` (`stats`, `bias`), `keeper.find`, `keeper.fidelity`, `keeper.growth` (`practice`, `residual`, `health`), `keeper.analysis` (`context`, `codeindex`, `pipeline`) | Methodology implementations (02-methodology) | platform (2), sources (1) |
| 2 Platform | `keeper.llm` (`gateway`, `providers`, `prompts`, `schemas`, `redact`, `meter`, `cache`, `batch`), `keeper.jobs` (`runner`, `local`, `nebius`, `events`), `keeper.sandbox` (`base`, `local`, `docker`, `contree`, `recipes`), `keeper.db` (`models`, `session`, `repo`), `keeper.config`, `keeper.logging`, `keeper.ids` | Cross-cutting infrastructure | sources (1), core (0) |
| 1 Sources | `keeper.sources.github` (`mirror`, `importer`, `client`), `keeper.sources.git`, `keeper.sources.junit`, `keeper.sources.osv`, `keeper.sources.tavily`, `keeper.sources.repo_files` (CODEOWNERS, pyproject, …) | Reading external formats | core (0) |
| 0 Core | `keeper.core` (`types`: Finding, Anchor, Lane, …; `taxonomy`; `timeutil`; `textsim`: TF-IDF helpers) | Pure types and helpers | nothing in `keeper` |
| Side | `keeper.datagen` | Data generation (build team) | everything except `keeper.app` and `keeper.assistant` |
| Side | `keeper.eval` (`truth`, `harness`, `report`) | Evaluation against ground truth | everything except `keeper.app` |

Special contracts:
- Only `keeper.llm.providers` may import `openai`.
- Only `keeper.sources.github.client` may call GitHub, and it exposes only `get_*` methods (G1).
- Only `keeper.eval` and `keeper.datagen` may read `data/ground_truth/`.
- `keeper.sandbox` is the only module that may spawn processes for untrusted code. `keeper.sources.git` may spawn `git`, with fixed argument lists and no shell.

## Module details

### `keeper.analysis.pipeline`
`analyze_pr(project, pr_number, *, lens_version, ruler, job) -> Analysis` orchestrates A1–A8 with caching per stage, emitting `analysis.step` events. It is idempotent per (head SHA, ruler, lens version).

### `keeper.lens.build`
`build_lens_version(person, *, cutoff, ruler, reason, job) -> LensVersion` runs L6 steps 1–12. It holds an advisory lock per lens; it writes everything in one transaction at the end (`status: building → ready`).

### `keeper.route.lanes`
Pure functions `route_findings(lens, baseline, matching, blind_spot_items, signals) -> list[RoutedFinding]` and `pr_lane(routed, signals) -> Lane`. There is no I/O, so they are property-testable.

### `keeper.fix`
`FixRunner(sandbox, gateway).run(analysis, finding_ids, *, branches, max_iterations, job)` implements the state machine, the branching and the events.

### `keeper.services.tour`
`build_tour(project) -> Tour` chooses the steps from data:
- aha PR = the held-out PR with the highest-severity maintainer finding that is R+ (missed by the baseline) **and** recovered by the lens in the latest fidelity run, preferring a `security` or `history_context` category and a diff of ≤ 120 lines;
- fix demo = the live-queue PR whose saved fix run has ≥ 1 failed attempt followed by a pass (so the repair is shown), preferring the `fix_demo` hint from the manifest if present;
- queue highlight = an `unknown` PR with ≥ 2 signals;
- practice taste item = an easy-to-medium item;
- each with reasons, so the UI never hardcodes PR numbers.

### `keeper.services.usage`
Aggregates `llm_calls` by model, feature and day; computes spend against caps.

## Error model

Domain errors are subclasses of `KeeperError(code, message, http_status, details)`: `NotFound`, `ConfirmationRequired(estimate)`, `SpendCapReached`, `ModelUnavailable(role)`, `RulerMismatch`, `ConsentRequired`, `SandboxUnavailable`, `RateLimited`, `ValidationFailed`. Routers map them to the API error format ([Conventions](../05-api/01-conventions.md) §4).

# Functional requirements (FRD)

Every requirement has a stable ID. Priority: **M** = must for v1, **S** = should, **C** = could. "Method" links point to the methodology that specifies the behaviour in detail; the requirement is the contract and the methodology is the algorithm.

## FR-DATA · Demo project and data loading

| ID | Requirement | P |
|---|---|---|
| FR-DATA-1 | On first start, the backend MUST load the demo project from `data/` (GitHub mirror JSON, git bundle, manifest) into the database and unpack the git bundle into `.runtime/repos/<project>/`. | M |
| FR-DATA-2 | Loading MUST verify `data/manifest.json` hashes and fail with a clear message if any file is missing or modified. | M |
| FR-DATA-3 | Loading MUST be idempotent: re-running it does not duplicate rows (natural keys are GitHub IDs). | M |
| FR-DATA-4 | When `data/snapshots/<project>/` exists, its pre-computed analyses (baseline, findings, residuals, lens versions, routes, review drafts, fix runs, fidelity runs, practice demo sessions) MUST be loaded and marked `origin = snapshot`. | M |
| FR-DATA-5 | The demo clock `demo_now` MUST come from the manifest; in demo mode all "today" logic uses it. | M |
| FR-DATA-6 | Ground truth (`data/ground_truth/`) MUST never be loaded into tables the pipeline reads; only `keeper.eval` reads it. | M |

## FR-IMP · Importing a real repository

| ID | Requirement | P |
|---|---|---|
| FR-IMP-1 | The user SHOULD be able to import a public GitHub repository by `owner/repo` with a maintainer login and a history window (`since`, default 36 months). | S |
| FR-IMP-2 | The importer MUST write raw API responses into the same mirror layout as the demo data (`.runtime/mirror/github/<owner>/<repo>/…`) and ingest them through the same adapter. | S |
| FR-IMP-3 | The importer MUST respect GitHub rate limits (read `x-ratelimit-remaining` and `x-ratelimit-reset`; sleep or stop), MUST use conditional requests (ETag) on re-import, and MUST be resumable. | S |
| FR-IMP-4 | Import MUST require an acknowledgement: "Review comments are their authors' copyright. Keeper uses them to evaluate and learn, attributes every quotation, and will not publish names without permission." The acknowledgement is stored as a `consent` row. | M (if import is built) |
| FR-IMP-5 | Every quotation from an imported project MUST show its author login and a link to the original comment. | M (if built) |
| FR-IMP-6 | An imported project's lens MUST be marked `consent_status = evaluation_only` until the maintainer is recorded as having opted in. In that state, Proof and analyses work, export is disabled, and the UI shows "For evaluation only". | M (if built) |
| FR-IMP-7 | The test runner for imported repositories MUST detect Python projects (`pyproject.toml`, `setup.cfg`, `setup.py`) and use `config/sandbox.yaml` recipes. Other ecosystems report "Fixes not available for this language yet". | S |

## FR-H · Human findings (what the maintainer noticed)

Method: [02-human-findings](../02-methodology/02-human-findings.md).

| ID | Requirement | P |
|---|---|---|
| FR-H-1 | Keeper MUST extract findings from each human's review comments (inline), review bodies, PR conversation comments, change-request states and rejections (closed without merge, with a closing comment). | M |
| FR-H-2 | One comment MAY yield several findings, or none ("LGTM", "thanks!"). | M |
| FR-H-3 | Each finding MUST have an anchor, a category from `config/taxonomy.yaml`, a severity, a kind, a `substantive` flag, a one-sentence statement and a link to its source comment IDs. | M |
| FR-H-4 | Replies in a thread MUST be attached to the thread's root finding, not counted as new findings, unless they raise a new concern. | M |
| FR-H-5 | Maintainer commits pushed to a contributor's PR (`committer` = maintainer, after a review) MUST be recorded as `kind = maintainer_fix` findings, derived from the commit diff. | S |
| FR-H-6 | Extraction MUST be cached per (comment IDs, prompt version, model) and re-run only when these change. | M |

## FR-BASE · The baseline (the ruler)

Method: [03-baseline-the-ruler](../02-methodology/03-baseline-the-ruler.md).

| ID | Requirement | P |
|---|---|---|
| FR-BASE-1 | Keeper MUST produce a baseline review C(S) for every analysed PR, using the `judge` model, the pinned `baseline_review` prompt and the decoding parameters from `config/baseline.yaml`. | M |
| FR-BASE-2 | The baseline MUST include static tools on changed lines (ruff and bandit for Python, with versions pinned in the backend lockfile), each mapped to taxonomy categories. | M |
| FR-BASE-3 | Each configuration MUST be stored as an immutable `ruler` (model ID, prompt ID, prompt hash, decoding parameters, tool versions, config hash). Any change creates a new ruler. | M |
| FR-BASE-4 | Residuals, lens builds and fidelity runs MUST reference exactly one ruler; comparing across rulers MUST be impossible through the API. | M |
| FR-BASE-5 | The baseline MUST see exactly the same PR context as the lens review (diff, description, file list, CI status), and nothing else. | M |
| FR-BASE-6 | The UI MUST let the user see the baseline's full output, labelled "Generic review", for any PR. | M |

## FR-RES · Matching and residual

Method: [04-matching-and-residual](../02-methodology/04-matching-and-residual.md).

| ID | Requirement | P |
|---|---|---|
| FR-RES-1 | For each PR and each pair of finding sets, Keeper MUST compute a one-to-one matching with `match`, `partial` or `none` decisions. | M |
| FR-RES-2 | Candidate pairs MUST be pre-filtered by code (anchor proximity, lexical similarity); only candidates go to the `match_findings` judge. | M |
| FR-RES-3 | The residual MUST partition the union into `shared`, `r_plus` and `r_minus`. Every finding appears in exactly one. | M |
| FR-RES-4 | Matching decisions MUST be stored with the judge's rationale and be viewable in the Proof case view. | M |
| FR-RES-5 | On the demo project, the judge's agreement with ground truth MUST be measured and shown in Proof ("How we measure"). | M |

## FR-LENS · Lens building, versions, packaging

Method: [05-lens](../02-methodology/05-lens-representation-and-building.md), [13-governance](../02-methodology/13-lens-versions-and-governance.md).

| ID | Requirement | P |
|---|---|---|
| FR-LENS-1 | A lens MUST be built only from a consenting person's findings, the residual against one ruler, and outcomes, with a training cutoff date. | M |
| FR-LENS-2 | Building MUST cluster R+ findings in code, then ask the `deep` model to name and describe each cluster as a lens item. Statistics MUST be computed by code, not by the model. | M |
| FR-LENS-3 | Each lens item MUST contain: title, statement, rationale, category, triggers (path globs, code patterns, PR features), exemplars (≥ `min_support` finding IDs), counter-examples, statistics and status. | M |
| FR-LENS-4 | Items with support below `min_support` MUST be `candidate`, not `validated`. | M |
| FR-LENS-5 | A lens MUST also hold **blind-spot items** (from calibrated R−) and **shared-ground items** (categories where the baseline suffices), each with statistics. | M |
| FR-LENS-6 | Keeper MUST generate a lens card (markdown) from the items. | M |
| FR-LENS-7 | The owner MUST be able to edit an item's wording, turn an item off (`disabled_by_owner`) and mark "This isn't me". All are logged and feed the next version. | M |
| FR-LENS-8 | New residual samples (feedback, new reviews) MUST be able to produce a new lens version on request. The previous version stays immutable. | M |
| FR-LENS-9 | Keeper MUST compute a lens diff between any two versions: added, retired, reworded, re-weighted, status changes. | M |
| FR-LENS-10 | After a rebuild, Keeper MUST re-run the fidelity test on the most recent held-out window and show the result alongside the diff. | S |
| FR-LENS-11 | Export MUST produce a skill package (`lens.json`, `LENS.md`, `SKILL.md`, `exemplars.jsonl`) that validates against `config/schemas/lens_package.schema.json`. | M |
| FR-LENS-12 | Import of a lens package MUST validate it and attach it to a person with consent. | S |

## FR-APPLY · Applying the lens to a PR

Method: [06-applying-the-lens](../02-methodology/06-applying-the-lens.md).

| ID | Requirement | P |
|---|---|---|
| FR-APPLY-1 | For a PR, Keeper MUST select relevant lens items and exemplars, using trigger evaluation in code plus a long-context recall step on the `fast` model (with BM25 as the fallback). | M |
| FR-APPLY-2 | Exemplar retrieval MUST only use findings created before the PR's `created_at` (no leakage). | M |
| FR-APPLY-3 | The `lens_review` prompt on the `judge` model MUST return findings that each cite ≥ 1 lens item ID and, where available, exemplar finding IDs. | M |
| FR-APPLY-4 | Lens findings with no valid citation MUST be dropped and counted in the run log. | M |
| FR-APPLY-5 | Each lens finding MUST carry a confidence (`low`, `medium`, `high`) derived by code from the cited items' calibration and the model's stated certainty. | M |
| FR-APPLY-6 | Disabled, retired and `bias_suspected` items MUST NOT be passed to the lens review as edge items. `bias_suspected` items are shown to the owner only. | M |

## FR-ROUTE · Routing into four cases, and hand-offs

Method: [07-routing-and-triage](../02-methodology/07-routing-and-triage.md).

| ID | Requirement | P |
|---|---|---|
| FR-ROUTE-1 | Every lens and baseline finding on a PR MUST be routed into exactly one lane. | M |
| FR-ROUTE-2 | A finding produced by both lens and baseline MUST route to `shared`. | M |
| FR-ROUTE-3 | A lens-only finding MUST route to `edge`. | M |
| FR-ROUTE-4 | A baseline-only finding MUST route to `blind_spot` only when it matches a calibrated blind-spot item of the maintainer's lens; otherwise it is kept as `baseline_only` (hidden under "Generic review also mentions"). | M |
| FR-ROUTE-5 | Risk signals from `config/routing.yaml` MUST be evaluated in code on every PR. Any fired signal not covered by a validated lens item MUST make the PR lane `unknown`. | M |
| FR-ROUTE-6 | A PR with any fired risk signal MUST NEVER have lane `shared`. | M |
| FR-ROUTE-7 | The PR lane MUST be the highest-priority lane among its routed findings and signals, in the order `unknown` > `edge` > `blind_spot` > `shared`. A PR with no findings is `shared`. | M |
| FR-ROUTE-8 | For `unknown` PRs, Keeper MUST propose hand-off candidates ranked by competence on the fired signals and lens distance from the maintainer, using people with lenses, CODEOWNERS entries and review history. | M |
| FR-ROUTE-9 | Keeper MUST draft a hand-off note naming the signals, the files, and what to look at. | M |
| FR-ROUTE-10 | For new dependencies, Keeper MUST query OSV and SHOULD query Tavily (when configured) and cite results in the note. | S |

## FR-TRI · Triage

| ID | Requirement | P |
|---|---|---|
| FR-TRI-1 | Keeper MUST triage all open PRs: run the analysis pipeline (or reuse a cached one for an unchanged head SHA), assign a lane and compute `attention_minutes`. | M |
| FR-TRI-2 | The attention formula MUST come from `config/routing.yaml`. | M |
| FR-TRI-3 | Keeper MUST compute an AI-slop score from content only. `author_association`, login and account age MUST NOT be inputs. | M |
| FR-TRI-4 | Slop PRs with no other findings MUST go to `shared` with a drafted, polite reply asking for specifics. Keeper never closes them. | M |
| FR-TRI-5 | Triage MUST run in the background on demand ("Refresh queue") and stream per-PR progress. | M |
| FR-TRI-6 | Each PR's triage MUST record a one-line summary and "why this lane" reasons. | M |
| FR-TRI-7 | Shared-lane fixable findings SHOULD be auto-fixed in the background when `auto_fix_shared` is true. | S |

## FR-Q · Queue (UI behaviour)

| ID | Requirement | P |
|---|---|---|
| FR-Q-1 | The queue MUST show open PRs grouped by lane, ordered `unknown`, `edge`, `blind_spot`, `shared`, and within a lane by attention descending. | M |
| FR-Q-2 | The header MUST show the count, the total attention and the budget ("41 of your 120 min"). | M |
| FR-Q-3 | Each row MUST show: number, title, author (with association badge), lane, summary, reasons as chips, attention, status (Fixed and tested, Draft ready, Waiting, Analysing). | M |
| FR-Q-4 | Filters: lane, label, author type; search by number or title. | S |
| FR-Q-5 | The user MUST be able to override a PR's lane; overrides are logged as feedback and never lower a risk-signal PR below `unknown`. | M |

## FR-REV · Pull request view and review draft

| ID | Requirement | P |
|---|---|---|
| FR-REV-1 | The PR view MUST show the diff, with routed findings anchored at their lines, each labelled with source ("Your lens", "Generic review", "Both"), lane, confidence, model and citations. | M |
| FR-REV-2 | For PRs with a human review (history and held-out), a **Compare** mode MUST show Generic review, the human's actual comments and Keeper side by side, with matches linked. | M |
| FR-REV-3 | Keeper MUST compose a review draft from the accepted and edited findings, grouped by severity, in the maintainer's preferred structure (learned style hints), with a header "Drafted by Keeper with Mira's lens v2. Not posted." | M |
| FR-REV-4 | The draft MUST be editable in place, and exportable as markdown (copy) and as GitHub review JSON (`{body, event, comments[]}`) for the user to post themselves. | M |
| FR-REV-5 | Every exported text MUST carry the Keeper label line from `config/review.yaml`. | M |
| FR-REV-6 | Citations MUST open the cited past PR at the cited comment. | M |

## FR-FB · Feedback

| ID | Requirement | P |
|---|---|---|
| FR-FB-1 | On each routed finding the maintainer MUST be able to **Accept**, **Edit** (text, severity), **Dismiss** (with an optional reason from a short list plus free text), or mark it a **Good catch** (blind spots). | M |
| FR-FB-2 | The maintainer MUST be able to **Add a note** that Keeper missed, anchored at a line. | M |
| FR-FB-3 | Each feedback event MUST be stored as a residual sample for the next lens version, with the PR, lens version and ruler. | M |
| FR-FB-4 | After ≥ `suggest_rebuild_after` new samples, the UI SHOULD offer "Update your lens", with a diff preview. | S |

## FR-FIX · The fix loop

Method: [08-fix-loop](../02-methodology/08-fix-loop.md).

| ID | Requirement | P |
|---|---|---|
| FR-FIX-1 | The user MUST be able to start a fix for one or more fixable findings on a PR. | M |
| FR-FIX-2 | The fix MUST run in a sandbox on a checkout of the PR head; the sandbox has no network by default and no secrets. | M |
| FR-FIX-3 | The sandbox provider MUST come from `SANDBOX_PROVIDER` (`contree`, `docker`, `local`). If the configured provider is unavailable, Keeper MUST fall back along `config/sandbox.yaml` and show the provider in use. | M |
| FR-FIX-4 | Before editing, Keeper MUST run the test suite once to record pre-existing failures. | M |
| FR-FIX-5 | The `deep` model MUST plan edits as structured search-and-replace operations. Code applies them; failures to apply are reported back to the model as repair input. | M |
| FR-FIX-6 | Keeper MUST support branching: start `branches` (default 2) candidate fixes from one checkpoint and keep the first that passes, or the smallest passing diff. | M |
| FR-FIX-7 | After applying, Keeper MUST run the targeted tests, then the full suite, then ruff on the changed lines. | M |
| FR-FIX-8 | On failure, Keeper MUST send truncated failure output to the `fix_repair` prompt and iterate up to `max_iterations`. | M |
| FR-FIX-9 | For edge findings whose lens items are `candidate` (not validated), Keeper MUST offer both the lens's fix and the baseline's suggestion as options ("build both, let reality decide"). | S |
| FR-FIX-10 | When the finding category is `tests` or a correctness change has no test, Keeper SHOULD add a regression test. | S |
| FR-FIX-11 | Results MUST be shown as a diff with a test log. Actions: Download patch, Copy as GitHub suggestion. Keeper MUST NOT push, merge or comment on GitHub. | M |
| FR-FIX-12 | Every attempt MUST stream its events (plan, apply, test output, result) to the UI. | M |
| FR-FIX-13 | A verification step (`fast` model) MUST check that the passing diff addresses the finding; "tests pass but the finding is not addressed" is reported as a failure. | M |

## FR-OUT · Outcomes

| ID | Requirement | P |
|---|---|---|
| FR-OUT-1 | Keeper MUST derive outcomes per PR from data: merged, closed unmerged, reverted (revert PR or a `This reverts commit` message), post-merge bug (a bug-labelled issue that links the PR, or whose fix PR touches lines the PR introduced, within `bug_window_days`), follow-up fix, CI failed. | M |
| FR-OUT-2 | Outcomes MUST be linked to the PR's findings by file and line overlap and by category, to measure whether a concern predicted the bad outcome. | M |

## FR-CAL · Calibration and bias

Method: [09-outcomes-calibration-bias](../02-methodology/09-outcomes-calibration-bias.md).

| ID | Requirement | P |
|---|---|---|
| FR-CAL-1 | For each lens item, Keeper MUST compute support, precision against the human on training data, and an outcome hit rate with a Beta posterior and a 90% credible interval. | M |
| FR-CAL-2 | Status transitions (`candidate` → `validated` → `retired`) MUST follow the thresholds in `config/lens.yaml`. | M |
| FR-CAL-3 | Blind-spot items MUST require outcome evidence (≥ `blind_spot_min_bad_outcomes`) before routing to `blind_spot`. | M |
| FR-CAL-4 | Recalibration MUST be runnable as a job (local or Nebius Serverless Job); the `deep` model writes explanations only. | M |
| FR-CAL-5 | Keeper MUST run a group-tracking check for each item across `author_association` groups, stratified by PR size and area. | M |
| FR-CAL-6 | Items failing the check without outcome support MUST become `bias_suspected` and be shown to the owner with the evidence. | M |
| FR-CAL-7 | All calibration numbers MUST show their sample size; below `min_support` the UI says "Not enough evidence yet". | M |

## FR-FIND · The edge map

| ID | Requirement | P |
|---|---|---|
| FR-FIND-1 | Keeper SHOULD compute, per area (path prefix × category), the residual rate, the cost (outcome-weighted), the volume and the speed of reality's answer. | S |
| FR-FIND-2 | It SHOULD rank areas by value and show the top N with evidence links. | S |
| FR-FIND-3 | It SHOULD show where generic review is enough (shared-dominant areas). | S |
| FR-FIND-4 | It SHOULD feed `attention_minutes` (areas with high value add attention). | C |

## FR-FID · The Perspective Fidelity Test

Method: [11-fidelity-test](../02-methodology/11-fidelity-test.md).

| ID | Requirement | P |
|---|---|---|
| FR-FID-1 | Keeper MUST run the fidelity test on held-out PRs (after the lens version's cutoff) for a chosen lens version and ruler. | M |
| FR-FID-2 | Metrics: substantive recall (lens, baseline, Keeper combined), residual recall, noise per PR, precision, caricature ratio and JSD, per-category recall, and routing accuracy (demo only). | M |
| FR-FID-3 | Keeper MUST report 95% bootstrap confidence intervals and a paired comparison against the baseline. | M |
| FR-FID-4 | No leakage: the lens version used MUST have a cutoff before every evaluated PR; exemplar retrieval is restricted per PR. | M |
| FR-FID-5 | The run MUST show its pass or fail against `config/fidelity.yaml` criteria. | M |
| FR-FID-6 | Each case MUST be inspectable (side-by-side and matches). | M |
| FR-FID-7 | Runs MUST be able to use the Batch API when `BATCH_API_ENABLED=true`. | S |
| FR-FID-8 | Keeper SHOULD support a "recent window" run after each lens rebuild. | S |
| FR-FID-9 | Proof MUST display the falsifiers from both papers as pass or fail checks computed from the run. | M |

## FR-GROW · Growth

Method: [12-growth-test-and-health](../02-methodology/12-growth-test-and-health.md).

| ID | Requirement | P |
|---|---|---|
| FR-GROW-1 | A learner MUST be able to take a **before** check of `k` held-out PRs without any Keeper output visible. | M |
| FR-GROW-2 | Learners MUST be able to anchor notes to lines or write PR-level notes. | M |
| FR-GROW-3 | Scoring MUST match learner notes to the target person's substantive findings (the `practice_score` prompt) and report recall, costly misses and the learner's own valid catches. | M |
| FR-GROW-4 | A **learn** session MUST follow review first, then a hint (not the answer), then a second try, then the reveal (the human's comments, the lens item, the explanation). | M |
| FR-GROW-5 | The **after** check MUST use a parallel form that is disjoint from before and learn and balanced on difficulty and category mix. | M |
| FR-GROW-6 | The progress view MUST show before and after, costly misses, own-eye catches, and a caveat about sample size. | M |
| FR-GROW-7 | For the maintainer, Keeper MUST compute the growth residual G against the previous lens version on PRs reviewed after its cutoff. | M |
| FR-GROW-8 | Keeper MUST compute per-period R+, costly R−, R+ hit rate and assisted-versus-unassisted signals where available. | M |
| FR-GROW-9 | Keeper MUST assign a health state using `config/growth.yaml` rules and explain it in plain words. | M |
| FR-GROW-10 | Learner profiles MUST be private to the learner unless they choose to share them. | M |
| FR-GROW-11 | The commons speed (absorption into the next model) is out of scope for v1 and MUST be documented as such in Proof's limits. | M |

## FR-GOV · Ownership and governance

Method: [13-lens-versions-and-governance](../02-methodology/13-lens-versions-and-governance.md).

| ID | Requirement | P |
|---|---|---|
| FR-GOV-1 | No lens MAY be built for a person without a `consent` row (demo personas have generated consent rows marked `synthetic`). | M |
| FR-GOV-2 | The owner MUST be able to pause a lens (no use, nothing deleted) and resume it. | M |
| FR-GOV-3 | Revoking MUST delete all lens versions, items and packages, keep an audit tombstone, and block rebuilding until consent is given again. | M |
| FR-GOV-4 | Lenses MUST be private by default: visible to the owner, and used in that project's routing. Sharing is a separate per-person grant. | M |
| FR-GOV-5 | Every item MUST carry provenance: source finding IDs, ruler ID, build job ID, and model IDs. | M |
| FR-GOV-6 | A learner using a maintainer's lens in Practice MUST see the maintainer credited. | M |
| FR-GOV-7 | Exported packages MUST include the licence or terms chosen by the owner (default "All rights reserved; personal use"). | S |
| FR-GOV-8 | An audit log MUST record lens builds, edits, exports, imports, pauses and revocations. | M |

## FR-ASK · The assistant

Method: [06-assistant](../04-architecture/06-assistant.md).

| ID | Requirement | P |
|---|---|---|
| FR-ASK-1 | Ask MUST offer a chat interface: thread list, message stream, input, suggested prompts. | M |
| FR-ASK-2 | Answers MUST stream token by token and show tool steps as collapsible lines ("Looked at PR #412"). | M |
| FR-ASK-3 | The assistant MUST answer only from tools over Keeper's data and cite PRs, comments and lens items as clickable cards. | M |
| FR-ASK-4 | Actions that cost money or change state (analyse, fix, rebuild lens, run Proof) MUST require an in-chat confirmation card with a cost estimate. | M |
| FR-ASK-5 | A context drawer (**Ask about this**) MUST be available on Queue, PR, Lens, Proof and Practice, pre-attaching the current context. | M |
| FR-ASK-6 | Threads MUST persist across sessions (database) and be deletable. | M |
| FR-ASK-7 | Without an API key, Ask MUST explain that it needs one and offer the suggested-answer examples from the snapshot (labelled as saved). | M |

## FR-TOUR · First run and the guided tour

| ID | Requirement | P |
|---|---|---|
| FR-TOUR-1 | On first visit (no `keeper.tour.v1` key in local storage), the guided tour MUST start with a skippable welcome card. | M |
| FR-TOUR-2 | The tour's steps and target PRs MUST be data-driven from `GET /api/v1/tour` (chosen from the snapshot and held-out set by `keeper.services.tour`), not hardcoded. | M |
| FR-TOUR-3 | A **Tour** button in the shell MUST restart it at any time. | M |
| FR-TOUR-4 | The tour MUST work in no-key mode, using saved results, labelled "Saved run". | M |

## FR-SET · Settings and modes

| ID | Requirement | P |
|---|---|---|
| FR-SET-1 | Settings MUST show the model provider status (configured or not), each role's model and probe result, without ever showing keys. | M |
| FR-SET-2 | Settings MUST show usage: calls, tokens and cost by model and by feature, and the remaining spend cap. | M |
| FR-SET-3 | Settings MUST let the user set the weekly attention budget, the auto-approve threshold, and the toggles from `config/ui.yaml` that are marked user-editable. These are stored in `settings_overrides`. | M |
| FR-SET-4 | Settings MUST show the sandbox provider in use and why (for example "Token Factory Sandboxes not enabled: using local runner"). | M |
| FR-SET-5 | Settings MUST list projects (demo or imported) and allow import (FR-IMP). | S |
| FR-SET-6 | In cloud mode (`KEEPER_AUTH_MODE=access_code`) a sign-in page MUST accept an access code and issue a session cookie. | M |
| FR-SET-7 | A role picker MUST let the user view as the maintainer or as a contributor (learner). In demo mode it lists demo personas, plus "Me (judge)" for Practice. | M |

## FR-LLM · Model use

| ID | Requirement | P |
|---|---|---|
| FR-LLM-1 | Every model call MUST go through the gateway, with role resolution, the fallback chain, retry, rate limit, spend cap, cache and audit. | M |
| FR-LLM-2 | Every UI element produced by a model MUST show the model display name and the latency. | M |
| FR-LLM-3 | Costly actions MUST show an estimate before running when above `KEEPER_AUTO_APPROVE_USD`. | M |

## FR-JOB · Jobs

| ID | Requirement | P |
|---|---|---|
| FR-JOB-1 | Long operations (triage, analyse, fix, lens build, recalibrate, fidelity, import, practice scoring) MUST run as jobs with persisted state and streamed events. | M |
| FR-JOB-2 | Jobs MUST be cancellable; cancellation stops new model calls and cleans up sandboxes. | M |
| FR-JOB-3 | On restart, jobs that were running MUST be marked `interrupted`, and MAY be resumed where idempotent. | M |
| FR-JOB-4 | `JOB_RUNNER=nebius` MUST submit lens rebuild, recalibration and fidelity jobs to Nebius Serverless Jobs. | S |

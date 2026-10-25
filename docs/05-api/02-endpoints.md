# Endpoints

All paths are under `/api/v1`. "Job" means the response is `202` with a job (see [Conventions](01-conventions.md) §5). "Confirm" means it may return `402 confirmation_required`. FR references point to the [FRD](../01-business/03-functional-requirements.md).

## 1. System

| Method and path | Purpose | Response (key fields) |
|---|---|---|
| `GET /health` | Liveness (no dependencies) | `{status: "ok"}` |
| `GET /status` | Readiness and what is available | `{mode, live: bool, reason_if_not_live, default_project_id, demo_now, models: [{role, model_id, display, probe: {exists, chat, json_schema, json_object, reasoning, tools}, fallback_active}], sandbox: {provider, reason}, spend: {used_usd, cap_usd, period, resets_at}, data: {manifest_sha, loaded_at, snapshot: bool}, version}` |
| `GET /tour` | Data-driven tour steps (FR-TOUR) | `{steps: [{id, title, body_md, route, target: {kind, id}, reason}]}` |
| `GET /glossary` | UI terms and tooltips | `{terms: [{key, label, short, long_md}]}` |
| `GET /avatars/{person_id}.svg` | A generated avatar (initials and colour from a hash; there are no photos) | SVG |

## 2. Auth (cloud mode only)

| Method and path | Purpose |
|---|---|
| `POST /auth/session {access_code}` | Sets the session and CSRF cookies; `204` |
| `DELETE /auth/session` | Sign out |
| `GET /auth/session` | `{signed_in, expires_at}` |

## 3. Projects and people

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /projects` | List projects | `{items: [{id, owner, repo, kind, fictional, counts: {pulls, open, reviewers}, primary_maintainer}]}` |
| `GET /projects/{pid}` | Project detail | Includes `demo_now`, the policy files present, the ruler ID |
| `POST /projects/import {repo_url, maintainer_login?, since?, max_pulls?}` | Import a public repository (FR-IMP) | Job (`import`, then optionally `learn`); `403` if `IMPORT_ALLOWED=false` |
| `DELETE /projects/{pid}` | Delete an imported project's data | Not allowed for the demo |
| `GET /projects/{pid}/people?role=` | People | `[{id, login, display_name, role, has_lens, lens_status, stats: {reviews, comments}}]` |
| `GET /projects/{pid}/people/{person_id}` | Person detail | Includes their lenses and consent state |
| `POST /projects/{pid}/people/{person_id}/consent {scope, attest: true}` | Record consent (FR-GOV) | |

## 4. Queue (FR-Q, FR-TRI)

| Method and path | Purpose | Response |
|---|---|---|
| `GET /projects/{pid}/queue?lane=&sort=&q=` | Open PRs with lanes | `{items: [QueueRow], summary: {by_lane: {shared, edge, blind_spot, unknown}, attention_minutes_total, budget_minutes, over_budget}, provenance}` |
| `POST /projects/{pid}/queue/refresh {numbers?}` | Re-triage (all or some) | Job (`triage`), Confirm |
| `GET /projects/{pid}/queue/digest` | A plain-language summary of this queue ("3 need your eye…") | `{markdown, cards}` (template plus data; no model call) |

`QueueRow`: `{number, title, author: {id, login, association, first_time}, lane, reasons: [{kind, label, detail}], signals: [{key, label}], attention_minutes, counts: {edge, blind_spot, shared, baseline_only}, slop: {score, label} | null, fix: {status, run_id} | null, handoff: {person_id} | null, updated_at, head_sha, analysis_id, provenance}`.

`sort`: `attention` (default: unknown first, then edge, blind spot, shared; within a lane by attention descending), `updated`, `number`.

## 5. Pull requests (FR-REV, FR-FB, FR-OUT)

| Method and path | Purpose | Response or notes |
|---|---|---|
| `GET /projects/{pid}/pulls/{n}` | PR header | `{number, title, body_md, author, state, labels, base, head, created_at, files: [{filename, status, additions, deletions}], checks: [{name, conclusion}], html_url}` |
| `GET /projects/{pid}/pulls/{n}/diff?file=` | Unified diff (per file, or all) | `{files: [{filename, patch, binary, too_large}]}` |
| `GET /projects/{pid}/pulls/{n}/analysis` | The current analysis | `{analysis_id, lane, summary_md, attention_minutes, signals, reasons, slop, recall_mode, findings: [RoutedFinding], baseline_only_count, stats, provenance}`; `404` if none |
| `POST /projects/{pid}/pulls/{n}/analysis` | (Re)analyse | Job (`analyze`), Confirm |
| `GET /projects/{pid}/pulls/{n}/compare` | The side-by-side view: what the baseline said and what the lens said | `{baseline: [Finding], lens: [Finding], pairs: [{baseline_id, lens_id, decision}], residual: {r_plus: [...], r_minus: [...]}}` |
| `GET /projects/{pid}/pulls/{n}/history?person_id=` | Past related comments by this person (same files or areas) | `{items: [{comment_id, pr_number, path, excerpt, at, html_url}]}` |
| `GET /projects/{pid}/pulls/{n}/human-review` | For held-out PRs only: what the maintainer actually wrote (used by Proof and Practice) | `403` for live PRs |
| `PATCH /projects/{pid}/findings/{rf_id} {state, text?, severity?}` | Accept, edit, dismiss or good catch (FR-FB) | The updated RoutedFinding; writes `feedback_events` |
| `POST /projects/{pid}/pulls/{n}/notes {path?, line?, text, category?}` | "Add what Keeper missed" | Creates a user note plus a feedback event |
| `POST /projects/{pid}/pulls/{n}/lane {lane, reason}` | Override the PR lane (raise only for non-owners; owners may lower except for risk signals) | |
| `GET /projects/{pid}/pulls/{n}/review-draft` | The review draft | `{body_md, comments: [{path, line, side, body_md, finding_id}], event: "COMMENT" | "REQUEST_CHANGES", edited_by_user, label: "Drafted by Keeper"}` |
| `PUT /projects/{pid}/pulls/{n}/review-draft {body_md, comments}` | Save edits | |
| `GET /projects/{pid}/pulls/{n}/review-draft/export?format=md|github_json` | Export (copy to clipboard or a file); `github_json` is the exact body of GitHub's "create a review" API so the user can post it themselves | Keeper never posts |
| `POST /projects/{pid}/pulls/{n}/handoff` | Suggest a reviewer (FR-TRI) | Job (`handoff`) → `Handoff` |
| `GET /projects/{pid}/pulls/{n}/handoff` | The latest hand-off | `{candidates: [{person_id, score, why}], target, note_md, checklist, osv, tavily}` |
| `GET /projects/{pid}/pulls/{n}/outcomes` | Known outcomes (held-out or past PRs) | |

`RoutedFinding`: `{id, lane, action, title, statement_md, rationale_md, suggestion_md, category, severity, kind, anchor: {scope, path, side, start_line, end_line}, confidence: "high" | "medium" | "low", fixable, evidence: {lens_items: [{id, title}], past_comments: [{id, pr_number, excerpt}], baseline_pair: {finding_id, statement} | null, blind_spot_item: {id, title} | null, signals: [...]}, user_state, user_text}`.

## 6. Fixes (FR-FIX)

| Method and path | Purpose | Notes |
|---|---|---|
| `POST /projects/{pid}/pulls/{n}/fixes {finding_ids, branches?, user_hint?}` | Start fix-and-test | Job (`fix`), Confirm; `409` if a fix for the same findings is running |
| `GET /projects/{pid}/pulls/{n}/fixes` | Fix runs for this PR | `{items: [FixRunSummary]}` |
| `GET /fixes/{fix_id}` | Fix run detail | `{status, provider, iterations, branches: [{name, attempts: [{iteration, step, plan_md, apply_errors, test: {passed, failed, failures: [{test, message}]}}]}], winning_branch, diff, diff_stats, junit_summary, cost_usd, provenance}` |
| `GET /fixes/{fix_id}/patch` | Download the winning diff as `.patch` | `text/x-diff` |
| `POST /fixes/{fix_id}/cancel` | Cancel | |

## 7. Lens (FR-LENS, FR-GOV, FR-CAL, FR-FIND)

| Method and path | Purpose | Response or notes |
|---|---|---|
| `GET /projects/{pid}/lenses` | Lenses in the project | `[{id, person, status, latest_version, health_state}]` |
| `GET /lenses/{lid}` | Lens overview | `{id, person, status, consent, versions: [{version, created_at, change_reason, origin}], current_version}` |
| `GET /lenses/{lid}/versions/{v}` | A version | `{version, card_md, cutoff_at, ruler_id, build_stats, items_count, provenance}` |
| `GET /lenses/{lid}/versions/{v}/items?type=&category=&status=&q=` | Items | `[LensItem]` |
| `GET /lens-items/{item_id}` | Item detail | Includes exemplars (with links to the original comments), counter-examples, stats (precision, Beta interval, support), bias check, triggers |
| `PATCH /lens-items/{item_id} {status?: "active"|"muted", edits?: {title?, statement?, severity_typical?}}` | Owner edits (create an owner override; take effect in the next analysis, recorded for the next version) | Owner only |
| `GET /lenses/{lid}/diff?from=&to=` | Version diff | `{added: [...], removed: [...], changed: [{item, fields: {name: {from, to}}}], summary_md}` |
| `POST /lenses/{lid}/rebuild {reason}` | Full rebuild | Job (`learn`), Confirm |
| `POST /lenses/{lid}/update` | Incremental update from feedback | Job (`lens_update`), Confirm; returns `400` if no unconsumed feedback |
| `POST /lenses/{lid}/recalibrate` | Recalibrate against outcomes | Job (`recalibrate`), Confirm |
| `POST /lenses/{lid}/pause` · `/resume` · `/revoke {confirm: "REVOKE"}` | Governance | Revoke deletes the items and digests and keeps an audit stub |
| `GET /lenses/{lid}/export` | A lens package (JSON, with the schema `config/schemas/lens_package.schema.json`) | Owner only |
| `POST /projects/{pid}/lenses/import` (multipart) | Import a package | Validated |
| `GET /lenses/{lid}/edge-map?version=` | The Find map (FR-FIND) | `{cells: [{area, category, volume, residual_rate, shared_rate, value, kind}], top: [...], enough: [...], gaps: [...], summary_md}` |
| `GET /lenses/{lid}/bias` | Bias checks | `[{item_id, title, odds_ratio, ci, verdict, n_by_group}]` |
| `GET /lenses/{lid}/growth` | Health and growth over time (FR-GROW) | `{health_state, explanation_md, snapshots: [{period, measures, state}]}` |
| `GET /lenses/{lid}/audit` | The audit trail | `[{at, actor_role, action, details}]` |

`LensItem`: `{id, stable_key, type, title, statement_md, category, severity_typical, triggers: {paths, symbols, keywords, signals}, stats: {support, precision_mean, precision_ci, recall_on_holdout, last_seen_at}, status, owner_override, provenance: {exemplar_count, first_seen_at}}`.

## 8. Proof (FR-FID)

| Method and path | Purpose | Response |
|---|---|---|
| `GET /projects/{pid}/fidelity-runs` | Runs | `[{id, lens_version, created_at, pass_overall, origin}]` |
| `GET /fidelity-runs/{fid}` | Run detail | `{holdout: {from, to, prs}, metrics: {system: {residual_recall, precision, f1, …}}, ci, pass: {criterion: bool}, falsifiers: [{name, description_md, result, pass}], cases_count, cost_usd, provenance}` |
| `GET /fidelity-runs/{fid}/cases?q=&outcome=` | Per-PR cases | `[{pr_number, title, maintainer_findings, baseline: {matched}, lens: {matched}, notes}]` |
| `GET /fidelity-runs/{fid}/cases/{n}` | A case side by side | The maintainer's findings, the baseline's findings, the lens's findings, with match lines |
| `POST /projects/{pid}/fidelity-runs {lens_version?, use_batch?}` | Run the Fidelity Test | Job (`fidelity`), Confirm |

## 9. Practice (FR-GROW)

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /projects/{pid}/practice/overview?learner=` | The learner's sessions, results, growth, and the next suggested session | `learner` = a person ID or `me` (guest key from the cookie) |
| `POST /projects/{pid}/practice/sessions {kind, target_person_id, length?}` | Start a session (`taste`, `before`, `learn`, `after`) | Items chosen from the item bank; returns the session with items (PR numbers only, no answers) |
| `GET /practice/sessions/{sid}` | The session | `{kind, items: [{pr_number, status}], current_index, status}` |
| `GET /practice/sessions/{sid}/items/{n}` | An item | `{pr: {title, body_md}, diff, files, hint_available}` (the diff without any Keeper findings) |
| `POST /practice/sessions/{sid}/items/{n}/answers {notes: [{scope, path?, line?, text}]}` | Submit an attempt | Job (`practice_score`) for scoring; small, so auto-approved |
| `GET /practice/sessions/{sid}/items/{n}/feedback` | Feedback after scoring. In `learn` after attempt 1 it returns only `hints`; the reveal (P's findings) comes after attempt 2 or for `taste` | `{attempt, hints: [{text, path?}] , reveal: {caught: [{note_id, finding}], missed: [{finding, why_it_matters_md, lens_item}], own_eye: [{note_id, why}], not_an_issue: [{note_id, line}]} | null, measures}` |
| `POST /practice/sessions/{sid}/complete` | Finish | `{result: {recall, costly_recall, costly_misses, own_eye, noise, growth: {recall, costly_recall, costly_misses} | null, learner_lens_diff: {started_catching, still_missing} | null, interpretation_md}}` (`growth` only for an `after` session with a matching `before`) |

## 10. Assistant (FR-ASK)

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /chat/threads?context=` | Threads | `[{id, title, context, updated_at}]` |
| `POST /chat/threads {context?}` | New thread | |
| `GET /chat/threads/{tid}` | Thread with messages | Messages: `{id, role, content_md, cards, tool_trace, created_at}` |
| `PATCH /chat/threads/{tid} {title}` | Rename | |
| `DELETE /chat/threads/{tid}` | Delete | |
| `POST /chat/threads/{tid}/messages {text, context?}` | Send; **the response is SSE** (`text/event-stream`) | See [Streaming events](03-streaming-events.md) §4 |
| `POST /chat/threads/{tid}/stop` | Stop the current answer | |
| `GET /chat/suggestions?context=` | Suggested prompts | `[{text, context}]` |
| `GET /chat/examples` | Saved examples for no-key mode | |

## 11. Jobs

| Method and path | Purpose |
|---|---|
| `GET /jobs?kind=&status=&limit=` | Recent jobs |
| `GET /jobs/{id}` | Status, progress, step, result, error, cost |
| `GET /jobs/{id}/events` | SSE (`Last-Event-ID` resume) |
| `GET /jobs/{id}/log` | The full text log |
| `POST /jobs/{id}/cancel` · `POST /jobs/{id}/resume` | |

## 12. Settings and usage (FR-SET)

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /settings` | Effective settings | `{editable: [{key, label, type, value, default, min, max, options}], readonly: {...}, secrets: {nebius_api_key: {configured: bool}, github_token: {...}, tavily_api_key: {...}}}` |
| `PATCH /settings {key: value}` | Update editable keys (validated against `config/ui.yaml` `editable_settings`) | |
| `POST /settings/reset {keys?}` | Restore defaults | |
| `GET /usage?period=day|month|total&group_by=model|feature|day` | Spend | `{rows: [{key, calls, input_tokens, output_tokens, cost_usd}], total, cap}` |
| `POST /settings/probe` | Re-run the model probe | Job |

## 13. Permissions

| Action | Who (`X-Keeper-Role`) |
|---|---|
| Read everything except held-out human reviews in live mode | anyone |
| Feedback on findings, review drafts, fixes, hand-offs, queue refresh | `maintainer` |
| Lens edits, pause, resume, revoke, export, rebuild | `maintainer` **and** the lens owner (in demo, the maintainer persona owns their lens) |
| Practice | anyone (scored as the selected learner) |
| Settings edits, import | `maintainer`; in cloud mode, import requires `IMPORT_ALLOWED=true` |

Demo mode trusts the role header (there is no real identity). The permission layer exists so that the workspace mode can attach real identities later.

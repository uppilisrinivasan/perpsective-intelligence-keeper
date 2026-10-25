# Internal data model (database)

SQLAlchemy 2.0 models in `keeper/db/models.py`, with Alembic migrations in `backend/migrations/`. SQLite locally (`.runtime/keeper.db`, WAL mode, `foreign_keys=ON`); PostgreSQL in the cloud (`DATABASE_URL`). Keeper's own IDs are ULIDs with a type prefix (`prj_`, `per_`, `fnd_`, …). GitHub IDs are kept as `gh_id` (bigint). All timestamps are UTC (`timestamptz` on PostgreSQL, ISO text on SQLite). JSON columns use the `JSON` type (JSONB on PostgreSQL).

## 1. Source tables (ingested from the mirror; read-only after ingest)

| Table | Key columns | Notes |
|---|---|---|
| `projects` | `id`, `owner`, `repo`, `kind` (`demo`, `imported`), `fictional`, `default_branch`, `primary_maintainer_id`, `demo_now`, `repo_path`, `mirror_path`, `created_at` | One row per workspace |
| `people` | `id`, `project_id`, `gh_id`, `login`, `display_name`, `type` (User, Bot), `role` (maintainer, reviewer, contributor, bot), `first_seen_at` | Unique (`project_id`, `gh_id`) |
| `pulls` | `id`, `project_id`, `number`, `gh_id`, `title`, `body`, `state`, `draft`, `author_id`, `author_association`, `created_at`, `updated_at`, `closed_at`, `merged_at`, `merged_by_id`, `merge_commit_sha`, `head_sha`, `head_ref`, `base_sha`, `base_ref`, `labels` (JSON), `additions`, `deletions`, `changed_files`, `split` (`train`, `holdout`, `live`; computed), `raw_path` | Unique (`project_id`, `number`) |
| `pull_files` | `pull_id`, `head_sha`, `filename`, `previous_filename`, `status`, `additions`, `deletions`, `patch` (text, nullable), `binary` | |
| `reviews` | `id`, `pull_id`, `gh_id`, `reviewer_id`, `state`, `body`, `submitted_at`, `commit_id`, `author_association` | |
| `review_comments` | `id`, `pull_id`, `gh_id`, `review_gh_id`, `in_reply_to_gh_id`, `author_id`, `path`, `line`, `start_line`, `side`, `start_side`, `original_line`, `subject_type`, `diff_hunk`, `body`, `commit_id`, `created_at`, `html_url` | |
| `issue_comments` | `id`, `project_id`, `issue_number`, `gh_id`, `author_id`, `body`, `created_at`, `html_url` | For both PRs and issues |
| `issues` | `id`, `project_id`, `number`, `gh_id`, `title`, `body`, `state`, `state_reason`, `author_id`, `labels` (JSON), `created_at`, `closed_at`, `is_pull` | |
| `timeline_events` | `id`, `project_id`, `issue_number`, `event`, `actor_id`, `created_at`, `commit_id`, `source_issue_number`, `payload` (JSON) | |
| `commits` | `sha`, `project_id`, `author_login`, `committer_login`, `authored_at`, `committed_at`, `message`, `parents` (JSON), `pull_numbers` (JSON) | |
| `check_runs` | `id`, `project_id`, `head_sha`, `name`, `status`, `conclusion`, `summary`, `completed_at` | |

## 2. Analysis tables

| Table | Key columns | Notes |
|---|---|---|
| `rulers` | `id` (content hash), `spec` (JSON), `created_at` | Immutable |
| `findings` | `id`, `project_id`, `pr_number`, `head_sha`, `source` (`human`, `baseline`, `lens`, `learner`), `person_id`, `ruler_id` (baseline), `lens_version_id` (lens), `practice_answer_id` (learner), `scope`, `path`, `side`, `start_line`, `end_line`, `category`, `severity`, `kind`, `statement`, `rationale`, `suggestion`, `substantive`, `confidence`, `refs` (JSON), `llm_call_id`, `origin` (`live`, `snapshot`), `created_at` | Indexes: (`project_id`, `pr_number`, `source`), (`person_id`, `created_at`) |
| `finding_matches` | `id`, `pr_number`, `set_a` (descriptor), `set_b`, `a_id`, `b_id`, `decision`, `weight`, `rationale`, `llm_call_id` | |
| `residual_samples` | `id`, `finding_id`, `person_id`, `ruler_id`, `class` (`shared`, `r_plus`, `r_minus`), `matched_finding_id`, `weight`, `evidence` (`review`, `accepted_suggestion`, `edited_suggestion`, `dismissed`, `added_note`, `maintainer_choice`) | |
| `outcomes` | `id`, `project_id`, `pr_number`, `kind`, `at`, `evidence` (JSON: revert SHA, issue number, fix PR) | |
| `outcome_links` | `outcome_id`, `finding_id`, `overlap` (JSON) | |
| `analyses` | `id`, `project_id`, `pr_number`, `head_sha`, `ruler_id`, `lens_version_id`, `status`, `pr_lane`, `attention_minutes`, `summary`, `slop_score`, `signals` (JSON), `reasons` (JSON), `recall_mode`, `stats` (JSON), `job_id`, `origin`, `created_at` | Unique (`pr_number`, `head_sha`, `ruler_id`, `lens_version_id`) |
| `routed_findings` | `id`, `analysis_id`, `finding_id` (lens or baseline), `paired_finding_id`, `lane` (`shared`, `edge`, `blind_spot`, `baseline_only`), `action`, `fixable`, `blind_spot_item_id`, `evidence` (JSON), `user_state` (`open`, `accepted`, `edited`, `dismissed`, `good_catch`), `user_text`, `user_severity` | |
| `handoffs` | `id`, `analysis_id`, `candidates` (JSON, ranked with scores), `target_person_id`, `note_md`, `checklist` (JSON), `osv` (JSON), `tavily` (JSON), `created_at` | |
| `review_drafts` | `id`, `analysis_id`, `body_md`, `comments` (JSON), `event`, `edited_by_user`, `updated_at` | |
| `feedback_events` | `id`, `project_id`, `pr_number`, `routed_finding_id`, `kind` (`accept`, `edit`, `dismiss`, `good_catch`, `add_note`, `lane_override`), `payload` (JSON), `lens_version_id`, `ruler_id`, `consumed_by_lens_version_id`, `at` | |
| `fix_runs` | `id`, `analysis_id`, `finding_ids` (JSON), `status`, `provider`, `winning_branch`, `diff` (text), `diff_stats` (JSON), `junit_summary` (JSON), `iterations`, `cost_usd`, `job_id`, `origin`, `created_at`, `finished_at` | |
| `fix_attempts` | `id`, `fix_run_id`, `branch` (`A`, `B`), `iteration`, `step` (`plan`, `repair`, `verify`), `llm_call_id`, `edits` (JSON), `apply_errors` (JSON), `test_result` (JSON), `log_path`, `started_at`, `finished_at` | |

## 3. Lens tables

| Table | Key columns | Notes |
|---|---|---|
| `consents` | `id`, `person_id`, `project_id`, `scope`, `granted_by`, `granted_at`, `revoked_at`, `text_version`, `synthetic` | |
| `lenses` | `id`, `person_id`, `project_id`, `status` (`active`, `paused`, `revoked`), `consent_id`, `shared_in_project`, `created_at` | FK to `consents` |
| `lens_versions` | `id`, `lens_id`, `version`, `cutoff_at`, `ruler_id`, `change_reason`, `parent_version_id`, `status` (`building`, `ready`, `failed`), `card_md`, `digest_path`, `digest_sha`, `build_stats` (JSON), `job_id`, `origin`, `created_at` | Unique (`lens_id`, `version`) |
| `lens_items` | `id`, `lens_version_id`, `stable_key`, `type`, `title`, `statement`, `rationale`, `category`, `severity_typical`, `triggers` (JSON), `stats` (JSON), `status`, `owner_override`, `owner_edits` (JSON), `provenance` (JSON) | `stable_key` keeps identity across versions |
| `lens_item_evidence` | `lens_item_id`, `finding_id`, `role` (`member`, `exemplar`, `counter_example`) | |
| `bias_checks` | `lens_item_id`, `odds_ratio`, `ci_low`, `ci_high`, `n_by_group` (JSON), `outcome_check` (JSON), `verdict` | |
| `edge_map_cells` | `lens_version_id`, `area`, `category`, `volume`, `residual_rate`, `shared_rate`, `cost`, `speed_days`, `tests_present`, `value`, `kind` (`top`, `enough`, `gap`) | |
| `growth_snapshots` | `id`, `lens_id`, `period_start`, `period_end`, `measures` (JSON), `health_state`, `explanation`, `created_at` | |
| `audit_events` | `id`, `at`, `actor_role`, `action`, `object_type`, `object_id`, `details` (JSON) | |

## 4. Evaluation and growth tables

| Table | Key columns |
|---|---|
| `fidelity_runs` | `id`, `project_id`, `person_id`, `lens_version_id`, `ruler_id`, `holdout_spec` (JSON), `status`, `metrics` (JSON), `ci` (JSON), `pass` (JSON), `falsifiers` (JSON), `batch_id`, `cost_usd`, `job_id`, `origin`, `created_at` |
| `fidelity_cases` | `run_id`, `pr_number`, `per_system` (JSON: counts and matched IDs), `notes` |
| `practice_sessions` | `id`, `project_id`, `learner_key` (a person ID, or `guest:<uuid>` for judges), `target_person_id`, `lens_version_id`, `kind` (`before`, `learn`, `after`, `taste`), `item_pr_numbers` (JSON), `status`, `result` (JSON), `origin`, `created_at` |
| `practice_answers` | `id`, `session_id`, `pr_number`, `attempt` (1, 2), `notes` (JSON: `[{scope, path, line, text}]`), `submitted_at`, `hints` (JSON) |

## 5. Platform tables

| Table | Key columns |
|---|---|
| `jobs` | `id`, `kind`, `status` (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`), `params` (JSON), `progress` (0–1), `step`, `result` (JSON), `error`, `runner` (`local`, `nebius`), `external_id`, `cost_usd`, `created_at`, `started_at`, `finished_at` |
| `job_events` | `id` (an autoincrement integer, used as the SSE `id`), `job_id`, `type`, `data` (JSON), `at` |
| `llm_calls` | `id`, `job_id`, `role`, `model_id`, `prompt_id`, `prompt_version`, `prompt_sha`, `request_hash`, `input_tokens`, `output_tokens`, `reasoning_tokens`, `cost_usd`, `latency_ms`, `cache_hit`, `fallback_from`, `status`, `error`, `feature` (queue, pr, fix, lens, proof, practice, ask, datagen), `at` |
| `llm_cache` | `request_hash`, `response` (JSON), `model_id`, `created_at` |
| `chat_threads` | `id`, `title`, `role`, `project_id`, `context` (JSON), `created_at`, `updated_at` |
| `chat_messages` | `id`, `thread_id`, `role` (`user`, `assistant`, `tool`), `content`, `tool_calls` (JSON), `tool_call_id`, `cards` (JSON), `llm_call_ids` (JSON), `created_at` |
| `settings_overrides` | `key`, `value` (JSON), `updated_at` |
| `sessions` | `id`, `created_at`, `last_seen_at`, `ip_hash` (cloud mode only) |

## 6. Snapshot loading

Snapshot rows are inserted with `origin = snapshot`. A live run for the same key (for example the same PR, head SHA, ruler and lens version) creates a new row with `origin = live`. Reads prefer `live` when present. **Reset to saved results** (Settings) deletes `origin = live` rows for the demo project.

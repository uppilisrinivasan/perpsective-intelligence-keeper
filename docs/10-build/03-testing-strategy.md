# Testing strategy

## 1. Layers

| Layer | Tool | Scope | Runs |
|---|---|---|---|
| Unit | pytest, hypothesis | Pure functions: routing, risk signals, attention, matching assignment, bootstrap, Beta posteriors, Mantel–Haenszel, forms, health rules, redaction, anchors, diff parsing | Every commit (`./run.sh --test`) |
| Integration | pytest with `LLM_PROVIDER=fake`, SQLite in a temp dir, the fixture mirror and a small git repository fixture | The pipelines end to end; jobs; the sandbox local runner on a tiny repository; snapshot loading | Every commit |
| API contract | pytest + `httpx.AsyncClient` | Each endpoint's status codes, schemas, errors, permissions, confirmations; the SSE event order; the OpenAPI snapshot | Every commit |
| Frontend unit | Vitest + Testing Library | Components in their states; hooks with MSW mocks; copy completeness | Every commit |
| E2E | Playwright against the real app with the fake provider and the committed data | The tour; Queue → PR → Compare → Fix; feedback → Update lens → diff; Ask with a confirmation card; Proof; Practice taste; Settings; no-key mode | CI on every PR; locally with `./run.sh --test e2e` |
| Responsive and visual | Playwright at the viewport matrix ([Responsive layout](../06-frontend/03-responsive-layout.md) §5) | No horizontal scroll, the primary action is visible, no clipped text; screenshots reviewed on change | CI |
| Accessibility | `@axe-core/playwright`, keyboard-only runs | Every screen | CI |
| Evaluation | `./run.sh --eval` (real models) | Methodology quality against the ground truth (`config/eval.yaml`) | Before the snapshot and the submission |
| Live smoke | `infra/nebius/smoke.sh` | The deployed app | After every deployment |

## 2. Must-have tests (named, because other documents cite them)

| Test | What it proves |
|---|---|
| `test_risk_signal_never_shared` (property-based) | For any findings and overrides, a PR with a high or medium signal never ends up `shared` (NFR-SAFE-2) |
| `test_uncovered_signal_forces_unknown` | Coverage rule |
| `test_lens_only_raises_attention` | Applying a lens never lowers a PR's lane or attention relative to baseline-only routing with the same signals |
| `test_baseline_never_falls_back` | A ruler call fails rather than silently using another model |
| `test_ruler_mismatch_rejected` | `409` across rulers |
| `test_no_leakage_in_fidelity` | Exemplars and digests used for a held-out PR all predate both the PR and the cutoff |
| `test_parallel_forms_balanced` | Practice forms within tolerances |
| `test_slop_ignores_author_association` | The bias guard on triage |
| `test_exported_review_has_keeper_label` | G2 |
| `test_github_client_get_only` | The GitHub client exposes no write methods and sends only GET |
| `test_consent_required_for_lens` | G4 |
| `test_revoke_deletes_lens_data` | Governance |
| `test_sandbox_commands_from_recipes_only` | Models cannot inject commands |
| `test_fix_never_deletes_tests` | A fix whose diff removes or skips tests is rejected |
| `test_citations_verified` | The assistant's unresolved markers are dropped |
| `test_no_secrets_in_repo` | Secret patterns over `git ls-files` |
| `test_env_example_complete` | Settings and `.env.example` agree |
| `test_mirror_validates_against_github_schemas` | Data schema fidelity (V1) |
| `test_edge_map_ranks_planted_areas_first` | Find |
| `test_data_manifest_hashes` | Committed data integrity |
| `test_spend_cap_blocks_calls` | Cost safety |
| `test_no_key_mode_serves_all_screens` | Every screen's endpoints return data from the snapshot without a key |
| `test_run_sh` (slow) | The one-command start ([run.sh](../08-run/01-run-sh.md) §5) |

## 3. Fixtures

- `backend/tests/fixtures/github/mini/`: a hand-written, schema-valid mirror of 6 PRs (written by the build, not generated), covering every endpoint type and edge case (outdated comments, multi-line comments, binary files, missing patches, pagination).
- `backend/tests/fixtures/repos/mini.bundle`: a tiny Python repository with a passing test suite and one PR that breaks a test (for the fix loop).
- `backend/tests/fixtures/llm/<prompt>/<case>.json`: recorded or hand-written model outputs; the fake provider's defaults produce schema-valid minimal outputs for any prompt.

## 4. CI (`.github/workflows/ci.yml`)

Jobs: `lint` (ruff, mypy, import-linter, eslint, tsc, stylelint, shellcheck), `secrets` (gitleaks on full history), `backend` (pytest with coverage ≥ 80% on `keeper/route`, `keeper/residual`, `keeper/fidelity`, `keeper/growth`, `keeper/calibrate`), `frontend` (Vitest), `e2e` (Playwright: Chromium for all viewports; WebKit and Firefox at 1440×900), `data` (manifest verify, schema validation), `api` (OpenAPI drift), and `run-sh` (macOS and Ubuntu clean-clone run). No job uses a real API key.

## 5. Evaluation runs

`./run.sh --eval` writes `data/generated/eval_report.json` and prints a table against `config/eval.yaml`. It is run before G12 (the snapshot) and before the submission. Results go into the README only from this report.

## 6. The hardcode guard

Requirement: **nothing is hardcoded** (no demo names, PR numbers, model IDs, thresholds, ports or copy in code).

`backend/tests/test_hardcode_guard.py` and `frontend/tests/unit/hardcode-guard.test.ts`:
1. **Demo values:** load the demo world's identifiers from `data/` (the repository name, the owner, all logins and display names, the PR numbers of the live queue and the tour, the slot IDs) and search `backend/keeper/**` and `frontend/src/**` for them as whole words. Any match fails, except in `keeper/datagen/**` (which reads them from the scenario) and in test fixtures.
2. **Model IDs:** the strings `nvidia/` and `Nemotron` may appear only in `config/`, `.env.example`, docs and the README; `frontend/src` may show display names only from the API.
3. **Ports and URLs:** `8430`, `5174`, `tokenfactory.nebius.com`, `api.github.com` and `osv.dev` may appear only in `config/`, `.env.example` and `keeper/config/settings.py` defaults.
4. **Thresholds:** for each numeric leaf in `config/{routing,lens,fidelity,growth,find,matching,fix}.yaml`, the AST scanner flags numeric literals with the same value in the corresponding `keeper/` package, with an allow-list for 0, 1, −1 and 2, plus explicit `# config-ok: <reason>` comments, which are reviewed.
5. **Copy:** JSX text nodes and string-literal props named `title`, `label`, `placeholder` or `aria-label` must come from `t()`; an ESLint rule (`keeper/no-literal-copy`) enforces this.
6. **Resolution:** CSS and class strings must not contain fixed layout widths or heights in px (`width: 1280px`, `h-[720px]`); `stylelint` and the ESLint rule check this. Borders (1px) and icons in em are allowed.

# Build log

What was built from these docs, how it was verified, and where the build differs from them.

## State (25 Oct 2026)

- **Runs locally:** `./run.sh` installs, builds and starts the app at http://127.0.0.1:8430 in no-key mode.
  `./run.sh --check` is green.
- **Backend:** every endpoint in `docs/05-api/02-endpoints.md` is implemented, and every job kind has a handler.
  Checks: 25 tests pass (1 skipped), ruff is clean, and the 3 import contracts hold.
- **Frontend:** 86 unit tests pass, type check and lint are clean, and the OpenAPI types match the backend. Queue,
  PR, Lens, Proof, Practice and Ask were checked in a headless browser against the running app.
- **Data:** `data/` is regenerated and verified (manifest), and V1–V9 pass. `data/snapshots/prj_demo/` holds the
  saved results (2.0 MB).
- **Live mode:** not exercised. No key was used during the build, so no Nemotron tokens were spent.

## Deviations from the docs

| Area | Docs | Build | Why |
|---|---|---|---|
| Data generation values | Values written by a model | Values authored in `config/datagen/world.yaml` and code templates (`keeper/datagen/codegen.py`); structure from code, real git and real pytest | No model spend during the build; the result is deterministic and reviewable. The manifest records this under `models_used.datagen`. |
| Snapshot | Produced by a real run | Produced with `LLM_PROVIDER=fake` (deterministic per-prompt simulators in `keeper/llm/simulate/`). `snapshot.json` has `"simulated": true`; the UI labels it "offline simulation" | No key during the build. Re-run `./run.sh --snapshot` with a key to replace it (it asks before spending). |
| Snapshot layout | Not specified | One JSON Lines file per table (`data/snapshots/prj_demo/*.jsonl`), plus `snapshot.json` and `chat_examples.jsonl` | Simple, diff-friendly, and loads with foreign keys in order. |
| Size budget | GitHub mirror within the original budget | Mirror budget 25 MB, total 35 MB (`keeper/datagen/validate.py`); CI JUnit gzipped (`*.xml.gz`), final heads only | The schema-exact mirror is larger than estimated. |
| GitHub schema | Exact | Review-comment `line`/`position` made nullable in the extracted schema | GitHub returns null for outdated comments, but the published schema doesn't allow it. |
| `config/ingest.yaml` | Not listed | Added (people roles, outcome keywords, import settings) | Keeps these values out of code (no-hardcoding rule). |
| Scenario knobs | — | `presence_intensity`, `activity_growth`, `history_quiet_days`, `max_slots_per_pr` in `scenario.yaml` | Needed to get enough planted signal per PR without leaving history PRs open. |
| Layer contract | Services import only pipelines | API schemas live in `keeper.app.schemas` and are imported by services; `.importlinter` enforces only the special contracts (openai only in providers; pipelines never import API, services or assistant; ground truth only from eval and datagen) | One schema module is shared by API and services. |
| Lens application in history | Retro application to past PRs | The lens is applied to held-out PRs (Proof) and the live queue only | Enough for every screen. Retro application would cost a model call per history PR. |
| Low-coverage signal | Per project | Per area (`low_lens_coverage` uses the person's findings in the PR's areas) | Fewer false "unknown" lanes. |
| Sensitivity analysis | Re-running with other matchers | Re-weighting match decisions (strict / lenient) on the stored pairs | No extra model calls. |
| Practice answers | Notes required | Empty answers allowed (score zero) | "I don't see anything" is a valid answer in a before/after check. |
| Relative times | — | On the demo clock, Keeper's own runs (after the frozen demo "now") show as "just now" | Without this, saved runs read "in 6 days". |
| Import a GitHub repo | Implemented | Not implemented; the job fails with `not_implemented` and a clear message | Out of time. The demo project works fully. |
| Eval harness | All metrics | Matching kappa and held-out routing F1 are reported as "not measured" | They need human labels, or history analyses this build doesn't make. |

## Honest results (offline simulation)

- **Proof (lens v1, 26 held-out PRs): not passed.** Keeper recall 0.31 vs generic 0.31; difference −0.01 (−0.18 to
  +0.16). Noise per PR 0.73 vs 2.35. The no-exaggeration criterion failed on category spread.
- **Eval:** 6 checks pass, 4 fail, 2 not measured (see `data/generated/eval_report.json`). The failures (extraction
  recall, routing F1, lens coverage, blind-spot items) are limits of the offline simulator's text heuristics, which
  stand in for Nemotron. Expect them to change with a live run; they are not tuned to pass.

## Next steps

1. With a key: `./run.sh --check` (probe), then `./run.sh --snapshot` and `./run.sh --eval`, then update the README
   numbers from the new run.
2. Implement `keeper/sources/github/importer.py` (GET-only mirror writer, then the normal ingest).
3. Add the remaining slow test (`test_run_sh`) and the e2e Playwright suite in CI.

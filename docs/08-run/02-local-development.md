# Local development

## 1. Daily loop

```bash
./run.sh --dev          # API on :8430 with reload, UI on :5174 with HMR
./run.sh --test         # before every commit (the pre-commit hooks run lint and the secret scan)
```

Open `http://127.0.0.1:5174` in dev (the Vite server proxies `/api`). The API docs are at `http://127.0.0.1:8430/api/docs`.

## 2. Working without spending money

- `LLM_PROVIDER=fake` in `.env` (or per command: `LLM_PROVIDER=fake ./run.sh --dev`) uses fixtures from `backend/tests/fixtures/llm/`. All screens work. Live actions return deterministic fixture results.
- With a key, `LLM_CACHE=true` (the default) means repeating an identical request costs nothing.
- Spend caps apply in dev too (`KEEPER_SPEND_CAP_USD`).

## 3. Recording fixtures

`python -m keeper.llm.record --prompt lens_review --case <name>` runs the real call once and stores the request and response under `backend/tests/fixtures/llm/<prompt>/<case>.json` (redacted). Fixtures must use the demo world only. The hardcode guard skips `tests/fixtures`, but the secret scan does not.

## 4. Useful commands

| Task | Command |
|---|---|
| Backend tests (fast) | `cd backend && .venv/bin/pytest -q -m "not slow"` |
| One test | `.venv/bin/pytest -q tests/route/test_lanes.py::test_risk_signal_never_shared` |
| Lint and types | `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy keeper` |
| Import layer contracts | `.venv/bin/lint-imports` |
| Frontend unit tests | `npm --prefix frontend test` |
| Frontend types and lint | `npm --prefix frontend run typecheck && npm --prefix frontend run lint` |
| E2E | `./run.sh --test e2e` |
| Regenerate API types | `npm --prefix frontend run api:gen` |
| New migration | `cd backend && .venv/bin/alembic revision --autogenerate -m "…"` |
| Inspect the database | `sqlite3 .runtime/keeper.db` |
| Re-run analysis for one PR | `python -m keeper.cli analyze --pr <n>` |
| Build a lens | `python -m keeper.cli learn --person <login>` |
| Run a fidelity test | `python -m keeper.cli fidelity` |
| Show spend | `python -m keeper.cli usage --period day` |

`keeper.cli` wraps the same services as the API, so it is useful for debugging pipelines without the UI.

## 5. Working on the frontend with saved data only

`./run.sh --dev` without a key gives the full UI from the snapshot. Most UI work needs no model calls. Storybook is not used. Instead, `/dev/components` (dev builds only) renders every catalog component in its states with fixture data, at adjustable container widths.

## 6. Branching and commits

Conventional commits (`feat(route): …`), citing requirement IDs in the body (`Implements FR-ROUTE-5`). CI must be green before merging to `main`.

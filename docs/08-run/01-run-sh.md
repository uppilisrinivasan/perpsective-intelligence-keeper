# `./run.sh`

**One command from the repository root starts everything:**

```bash
./run.sh
```

On a clean clone it checks the prerequisites, creates `.env`, installs the backend and frontend, builds the frontend, loads the committed demo data, starts Keeper at `http://127.0.0.1:8430` (or `APP_PORT`), and opens the browser. Without an API key it runs in saved-results mode; with `NEBIUS_API_KEY` in `.env` it runs live.

## 1. Flags

| Command | What it does |
|---|---|
| `./run.sh` | Install if needed, build if needed, start the app (production build, one process) |
| `./run.sh --dev` | Backend with auto-reload + Vite dev server with HMR (on `FRONTEND_DEV_PORT`, proxying `/api`); installs pre-commit hooks |
| `./run.sh --check` | Diagnostics, without starting: prerequisites, `.env` validity, config schema validation, the data manifest's hashes, the model probe (if a key is set), the sandbox provider, the secret scan, and the ports. Exits non-zero on errors. |
| `./run.sh --test` | Backend tests (pytest, `LLM_PROVIDER=fake`, offline), frontend unit tests (Vitest), type checks, lint; `--test e2e` adds Playwright (it starts the app on a free port with the fake provider) |
| `./run.sh --eval` | The evaluation harness against the ground truth (needs a key; asks to confirm the estimated cost) |
| `./run.sh --generate-data` | Build team only: regenerate `data/` (datagen run → validate → snapshot), with cost confirmation |
| `./run.sh --snapshot` | Re-run the snapshot stage only (G12) |
| `./run.sh --reset` | Delete `.runtime/` (database, caches, sandboxes, logs) after confirmation; `data/` and `.env` are untouched |
| `./run.sh --port <n>` | Override `APP_PORT` for this run |
| `./run.sh --no-browser` | Don't open the browser |
| `./run.sh --help` | Usage |

Flags combine where sensible (`./run.sh --dev --port 8500`).

## 2. What it does, step by step

| # | Step | Details | On failure |
|---|---|---|---|
| 1 | Locate the root | `cd "$(dirname "$0")"`; `set -euo pipefail` | — |
| 2 | Prerequisites | Python ≥ 3.11 (`python3.13`, `python3.12`, `python3.11`, `python3`, in that order), Node ≥ 20.19, npm, git ≥ 2.34. Optional: `uv` (faster installs), Docker (sandbox) | Prints what is missing and the install hint for macOS (Homebrew) and Linux (apt/dnf); exits 1 |
| 3 | `.env` | If missing: copy `.env.example` → `.env`, `chmod 600`, print "Created .env. Add NEBIUS_API_KEY to run live (optional)." Never print values. | — |
| 4 | Load `.env` | For the script's own use only (`APP_PORT`, `APP_HOST`, `FRONTEND_DEV_PORT`, `OPEN_BROWSER`, `KEEPER_RUNTIME_DIR`), parsed safely (no `source` of arbitrary code: a small `while read` parser accepting `KEY=VALUE` lines) | Bad lines are reported with line numbers |
| 5 | Backend install | If `backend/.venv` is missing or `backend/uv.lock` (or `requirements.lock`) changed (hash stored in `.runtime/install.hash`): `uv sync --frozen` in `backend/`, or `python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.lock -e backend` | Shows the pip/uv error tail |
| 6 | Frontend install | If `frontend/node_modules` is missing or `package-lock.json` changed: `npm ci --prefix frontend` | — |
| 7 | API types | `backend/.venv/bin/python -m keeper.app.export_openapi > frontend/src/api/openapi.json` and `npm run --prefix frontend api:gen` if the backend changed | — |
| 8 | Frontend build | If any file in `frontend/src` (or the config files) is newer than `frontend/dist/.build-stamp`: `npm run --prefix frontend build` (skipped in `--dev`) | — |
| 9 | Sandbox wheelhouse | If `.runtime/wheels/python-pytest` is missing: `pip download -r backend/sandbox-requirements.txt -d .runtime/wheels/python-pytest` | Warning only (fixes will then fail with a clear message) |
| 10 | Runtime dirs | `mkdir -p .runtime/{cache,logs,sandboxes,projects}` | — |
| 11 | Migrations | `python -m keeper.db upgrade` (Alembic) | — |
| 12 | Port | If `APP_PORT` is in use: print the process (`lsof -i :PORT`) and suggest `./run.sh --port <free>`; exit 1 | — |
| 13 | Start | `exec backend/.venv/bin/python -m keeper.app --host "$APP_HOST" --port "$APP_PORT"` (Uvicorn inside). On startup the app verifies the data manifest, enqueues `load_demo` if the database is empty or the manifest changed, and starts the model probe in the background. | — |
| 14 | Browser | When `/api/v1/health` answers (polled up to 30 s), open the URL (`open` on macOS, `xdg-open` on Linux) if `OPEN_BROWSER=true` and not `--no-browser` | — |

`--dev` runs step 13 as `uvicorn keeper.app:create_app --factory --reload` and starts `npm run --prefix frontend dev` in parallel, with both processes' output prefixed (`[api]`, `[web]`). Ctrl-C stops both (a trap kills the process group).

## 3. Output (what the user sees)

```
Keeper
  ✓ Python 3.12.6   ✓ Node 22.11.0   ✓ git 2.47.0   · Docker not found (tests will use the local sandbox)
  ✓ .env found      · No NEBIUS_API_KEY: starting with saved results (add a key to run live)
  ✓ Backend ready   ✓ Frontend built   ✓ Data verified (manifest 3f9c…, 31.8 MB)
  → Keeper is running at http://127.0.0.1:8430   (Ctrl-C to stop)
```

## 4. Platform notes

- macOS (Apple Silicon and Intel) and Linux are supported. On Windows, use WSL2 (documented in [Troubleshooting](03-troubleshooting.md)).
- The script is POSIX bash (≥ 3.2, because macOS ships 3.2): no associative arrays or `${var,,}`. It is checked with `shellcheck` in CI.
- It never needs `sudo`, and it never installs system packages itself.

## 5. Acceptance tests for `run.sh`

`backend/tests/test_run_sh.py` (marked `slow`; runs in CI on Ubuntu and macOS) checks: a clean clone reaches `/api/v1/health` in no-key mode; `.env` is created with mode 600; a second run starts in ≤ 10 s (NFR-PERF-1); `--check` exits 0 on a good setup and 1 on a missing prerequisite (simulated through `PATH`); `--reset` keeps `data/` and `.env`.

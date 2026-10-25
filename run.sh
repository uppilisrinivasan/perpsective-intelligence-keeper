#!/usr/bin/env bash
# Keeper: one command to install, build and start (docs/08-run/01-run-sh.md). POSIX bash ≥ 3.2 (macOS).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

DEV=0; CHECK=0; TEST=0; TEST_E2E=0; EVAL=0; GEN=0; SNAP=0; RESET=0; NO_BROWSER=0; PORT_OVERRIDE=""
usage() {
  cat <<'EOF'
Usage: ./run.sh [options]

  (no options)      Install if needed, build if needed, start Keeper (one process)
  --dev             Backend with auto-reload + Vite dev server with HMR
  --check           Diagnostics only (prerequisites, .env, config, data manifest, model probe, sandbox, ports)
  --test [e2e]      Backend tests (offline), frontend tests, type checks and lint; "e2e" adds Playwright
  --eval            Evaluation harness against the ground truth (needs a key; asks before spending)
  --generate-data   Regenerate data/ (datagen run → validate → snapshot)
  --snapshot        Re-run the snapshot stage only
  --reset           Delete .runtime/ (database, caches, sandboxes, logs); data/ and .env are kept
  --port <n>        Use this port instead of APP_PORT
  --no-browser      Don't open the browser
  --help            This help
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --dev) DEV=1 ;;
    --check) CHECK=1 ;;
    --test) TEST=1; if [ "${2:-}" = "e2e" ]; then TEST_E2E=1; shift; fi ;;
    --eval) EVAL=1 ;;
    --generate-data) GEN=1 ;;
    --snapshot) SNAP=1 ;;
    --reset) RESET=1 ;;
    --port) PORT_OVERRIDE="${2:-}"; [ -n "$PORT_OVERRIDE" ] || { echo "--port needs a number" >&2; exit 2; }; shift ;;
    --no-browser) NO_BROWSER=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
info() { printf '  · %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; }

echo "Keeper"

# ---------------------------------------------------------------------------------------------- reset
if [ "$RESET" = 1 ]; then
  printf 'Delete .runtime/ (database, caches, sandboxes, logs)? data/ and .env are kept. [y/N] '
  read -r ans
  case "$ans" in y|Y|yes) rm -rf "$ROOT/.runtime"; ok "Deleted .runtime/"; exit 0 ;; *) info "Nothing deleted"; exit 0 ;; esac
fi

# --------------------------------------------------------------------------------------- prerequisites
ver_ge() { # ver_ge 3.12.1 3.11  → true when $1 ≥ $2
  [ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -1)" = "$2" ]
}
MISSING=0
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v="$("$c" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo 0)"
    if ver_ge "$v" 3.11; then PY="$c"; PYV="$v"; break; fi
  fi
done
LINE=""
if [ -n "$PY" ]; then LINE="✓ Python $PYV"; else fail "Python ≥ 3.11 not found (macOS: brew install python@3.12; Linux: apt install python3.12)"; MISSING=1; fi
if command -v node >/dev/null 2>&1 && ver_ge "$(node -v | tr -d v)" 20.19; then LINE="$LINE   ✓ Node $(node -v | tr -d v)"
else fail "Node ≥ 20.19 not found (macOS: brew install node; Linux: see nodejs.org)"; MISSING=1; fi
command -v npm >/dev/null 2>&1 || { fail "npm not found (it comes with Node)"; MISSING=1; }
if command -v git >/dev/null 2>&1 && ver_ge "$(git --version | awk '{print $3}')" 2.34; then LINE="$LINE   ✓ git $(git --version | awk '{print $3}')"
else fail "git ≥ 2.34 not found (macOS: brew install git; Linux: apt install git)"; MISSING=1; fi
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then LINE="$LINE   ✓ Docker"
else LINE="$LINE   · Docker not running (fixes will use the local sandbox)"; fi
[ "$MISSING" = 0 ] || exit 1
printf '  %s\n' "$LINE"

# ------------------------------------------------------------------------------------------------ .env
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  ok "Created .env. Add NEBIUS_API_KEY to run live (optional)."
else
  ok ".env found"
fi
# A small KEY=VALUE reader for the script's own settings (never `source`d, values never printed).
APP_HOST="127.0.0.1"; APP_PORT="8430"; FRONTEND_DEV_PORT="5173"; OPEN_BROWSER="true"; KEEPER_RUNTIME_DIR=".runtime"
HAS_KEY=0; PROVIDER="nebius"; n=0
while IFS= read -r line || [ -n "$line" ]; do
  n=$((n + 1))
  case "$line" in ''|\#*) continue ;; esac
  case "$line" in
    *=*) k="${line%%=*}"; v="${line#*=}" ;;
    *) warn ".env line $n is not KEY=VALUE (ignored)"; continue ;;
  esac
  k="$(printf '%s' "$k" | tr -d '[:space:]')"
  v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  case "$k" in
    APP_HOST) APP_HOST="$v" ;;
    APP_PORT) APP_PORT="$v" ;;
    FRONTEND_DEV_PORT) FRONTEND_DEV_PORT="$v" ;;
    OPEN_BROWSER) OPEN_BROWSER="$v" ;;
    KEEPER_RUNTIME_DIR) [ -n "$v" ] && KEEPER_RUNTIME_DIR="$v" ;;
    LLM_PROVIDER) [ -n "$v" ] && PROVIDER="$v" ;;
    NEBIUS_API_KEY|LLM_API_KEY) [ -n "$v" ] && HAS_KEY=1 ;;
    *[!A-Za-z0-9_]*) warn ".env line $n has an invalid key name (ignored)" ;;
  esac
done < .env
[ -n "${LLM_PROVIDER:-}" ] && PROVIDER="$LLM_PROVIDER"
[ -n "$PORT_OVERRIDE" ] && APP_PORT="$PORT_OVERRIDE"
export APP_PORT APP_HOST
if [ "$PROVIDER" = "fake" ]; then info "LLM_PROVIDER=fake: offline simulator (results are labelled simulated)"
elif [ "$HAS_KEY" = 1 ]; then ok "API key set: live mode"
else info "No NEBIUS_API_KEY: starting with saved results (add a key to run live)"; fi
case "$KEEPER_RUNTIME_DIR" in /*) RT="$KEEPER_RUNTIME_DIR" ;; *) RT="$ROOT/$KEEPER_RUNTIME_DIR" ;; esac
mkdir -p "$RT"/cache "$RT"/logs "$RT"/sandboxes "$RT"/projects

hash_of() { cat "$@" 2>/dev/null | shasum -a 256 | awk '{print $1}'; }

# ------------------------------------------------------------------------------------------- backend
VENV="$ROOT/backend/.venv"
VPY="$VENV/bin/python"
want="$(hash_of backend/requirements.lock backend/pyproject.toml)"
have="$(cat "$RT/install.hash" 2>/dev/null || true)"
if [ ! -x "$VPY" ] || [ "$want" != "$have" ]; then
  info "Installing the backend…"
  if command -v uv >/dev/null 2>&1 && [ -f backend/uv.lock ]; then
    (cd backend && uv sync --frozen) >"$RT/logs/install.log" 2>&1 || { fail "Backend install failed:"; tail -20 "$RT/logs/install.log" >&2; exit 1; }
  else
    { [ -x "$VPY" ] || "$PY" -m venv "$VENV"; } >"$RT/logs/install.log" 2>&1
    { "$VPY" -m pip install -q --upgrade pip && "$VPY" -m pip install -q -r backend/requirements.lock && "$VPY" -m pip install -q --no-deps -e backend; } \
      >>"$RT/logs/install.log" 2>&1 || { fail "Backend install failed:"; tail -20 "$RT/logs/install.log" >&2; exit 1; }
  fi
  printf '%s' "$want" >"$RT/install.hash"
fi
BACKEND_LINE="✓ Backend ready"

# ------------------------------------------------------------------------------------------ frontend
npm_ci() {
  if ! npm ci --prefix frontend --no-audit --no-fund >"$RT/logs/npm.log" 2>&1; then
    # Some machines have a root-owned ~/.npm; fall back to a project-local cache.
    npm ci --prefix frontend --no-audit --no-fund --cache "$RT/npm-cache" >"$RT/logs/npm.log" 2>&1 || {
      fail "Frontend install failed:"; tail -20 "$RT/logs/npm.log" >&2; exit 1; }
  fi
}
want_fe="$(hash_of frontend/package-lock.json)"
have_fe="$(cat "$RT/npm.hash" 2>/dev/null || true)"
if [ ! -d frontend/node_modules ] || [ "$want_fe" != "$have_fe" ]; then
  info "Installing the frontend…"
  npm_ci
  printf '%s' "$want_fe" >"$RT/npm.hash"
fi

# API types: regenerate when the backend's API changed
api_hash="$(find backend/keeper/app -name '*.py' -newer frontend/src/api/openapi.json 2>/dev/null | head -1)"
if [ ! -f frontend/src/api/openapi.json ] || [ -n "$api_hash" ]; then
  (cd backend && "$VPY" -m keeper.app.export_openapi >../frontend/src/api/openapi.json.tmp) && \
    mv frontend/src/api/openapi.json.tmp frontend/src/api/openapi.json && \
    npm run --silent --prefix frontend api:gen >"$RT/logs/api-gen.log" 2>&1 || warn "API type generation failed (see .runtime/logs/api-gen.log)"
fi

FRONT_LINE=""
if [ "$DEV" = 0 ] && [ "$CHECK" = 0 ]; then
  stamp=frontend/dist/.build-stamp
  newer=""
  if [ -f "$stamp" ]; then
    newer="$(find frontend/src frontend/index.html frontend/vite.config.ts frontend/package.json frontend/tsconfig.json frontend/public -newer "$stamp" -type f 2>/dev/null | head -1)"
  fi
  if [ ! -f "$stamp" ] || [ -n "$newer" ]; then
    info "Building the frontend…"
    npm run --prefix frontend build >"$RT/logs/frontend-build.log" 2>&1 || { fail "Frontend build failed:"; tail -30 "$RT/logs/frontend-build.log" >&2; exit 1; }
  fi
  FRONT_LINE="✓ Frontend built"
fi

# ------------------------------------------------------------------------------------- sandbox wheels
WH="$RT/wheels/python-pytest"
if [ ! -d "$WH" ] || [ -z "$(ls -A "$WH" 2>/dev/null)" ]; then
  mkdir -p "$WH"
  "$VPY" -m pip download -q -r backend/sandbox-requirements.txt -d "$WH" --only-binary=:all: >"$RT/logs/wheels.log" 2>&1 \
    || warn "Couldn't download the test wheelhouse (offline?). Fixes will report this until it is downloaded."
fi

# ---------------------------------------------------------------------------------- one-shot commands
run_py() { (cd backend && "$VPY" "$@"); }
if [ "$CHECK" = 1 ]; then printf '  %s   %s\n' "$BACKEND_LINE" "$FRONT_LINE"; exec_status=0; run_py -m keeper.cli check --port "$APP_PORT" || exec_status=$?; exit $exec_status; fi
if [ "$TEST" = 1 ]; then
  st=0
  info "Backend tests (offline)…"
  (cd backend && LLM_PROVIDER=fake "$VPY" -m pytest -q) || st=1
  (cd backend && "$VPY" -m ruff check keeper) || st=1
  info "Frontend tests, types and lint…"
  npm run --silent --prefix frontend test || st=1
  npm run --silent --prefix frontend typecheck || st=1
  npm run --silent --prefix frontend lint || st=1
  if [ "$TEST_E2E" = 1 ]; then (cd frontend && npx playwright test) || st=1; fi
  [ "$st" = 0 ] && ok "All checks passed" || fail "Some checks failed"
  exit $st
fi
if [ "$EVAL" = 1 ]; then run_py -m keeper.cli eval; exit $?; fi
if [ "$GEN" = 1 ]; then run_py -m keeper.datagen run && run_py -m keeper.datagen validate && run_py -m keeper.datagen snapshot; exit $?; fi
if [ "$SNAP" = 1 ]; then run_py -m keeper.datagen snapshot; exit $?; fi

# ------------------------------------------------------------------------------------- migrate, start
run_py -m keeper.db upgrade >"$RT/logs/migrate.log" 2>&1 || { fail "Database migration failed:"; tail -20 "$RT/logs/migrate.log" >&2; exit 1; }
DATA_LINE="$(run_py -m keeper.cli data-line 2>/dev/null || echo '· Data not verified')"
printf '  %s   %s   %s\n' "$BACKEND_LINE" "${FRONT_LINE:-· Frontend dev server}" "$DATA_LINE"

port_busy() { "$VPY" - "$1" "$2" <<'EOF'
import socket, sys
s = socket.socket()
try:
    s.bind((sys.argv[1], int(sys.argv[2])))
except OSError:
    sys.exit(0)
sys.exit(1)
EOF
}
if port_busy "$APP_HOST" "$APP_PORT"; then
  fail "Port $APP_PORT is in use:"
  (lsof -i ":$APP_PORT" 2>/dev/null | head -5) >&2 || true
  echo "    Try: ./run.sh --port <free port>" >&2
  exit 1
fi

URL="http://$APP_HOST:$APP_PORT"
open_browser() {
  [ "$NO_BROWSER" = 0 ] && [ "$OPEN_BROWSER" = "true" ] || return 0
  target="$1"
  for _ in $(seq 1 60); do
    if "$VPY" -c "import urllib.request,sys; urllib.request.urlopen(sys.argv[1], timeout=1)" "$URL/api/v1/health" >/dev/null 2>&1; then
      if command -v open >/dev/null 2>&1; then open "$target"; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$target" >/dev/null 2>&1; fi
      return 0
    fi
    sleep 0.5
  done
}

if [ "$DEV" = 1 ]; then
  if command -v pre-commit >/dev/null 2>&1 && [ -d .git ]; then pre-commit install >/dev/null 2>&1 || true; fi
  WEB="http://$APP_HOST:$FRONTEND_DEV_PORT"
  echo "  → API at $URL, app at $WEB   (Ctrl-C to stop)"
  trap 'kill 0' INT TERM EXIT
  (cd backend && "$VPY" -m keeper.app --host "$APP_HOST" --port "$APP_PORT" --reload 2>&1 | sed -u 's/^/[api] /') &
  (VITE_API_PORT="$APP_PORT" npm run --prefix frontend dev -- --host "$APP_HOST" --port "$FRONTEND_DEV_PORT" 2>&1 | sed -u 's/^/[web] /') &
  open_browser "$WEB" &
  wait
  exit 0
fi

echo "  → Keeper is running at $URL   (Ctrl-C to stop)"
open_browser "$URL" &
cd backend
exec "$VPY" -m keeper.app --host "$APP_HOST" --port "$APP_PORT"

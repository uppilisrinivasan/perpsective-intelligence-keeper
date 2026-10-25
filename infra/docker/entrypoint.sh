#!/bin/sh
# Container start: migrate, link the baked wheelhouse into the runtime dir, then run the app.
set -eu
cd /app/backend
mkdir -p "$KEEPER_RUNTIME_DIR/wheels"
[ -e "$KEEPER_RUNTIME_DIR/wheels/python-pytest" ] || ln -s /opt/keeper/wheels/python-pytest "$KEEPER_RUNTIME_DIR/wheels/python-pytest"
python -m keeper.db upgrade
exec python -m keeper.app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8430}"

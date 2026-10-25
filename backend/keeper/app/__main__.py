"""python -m keeper.app --host H --port P (run.sh step 13)."""

from __future__ import annotations

import argparse
import sys

import uvicorn


def main() -> int:
    from keeper.config import get_settings
    from keeper.config.settings import StartupError, validate_startup

    s = get_settings()
    ap = argparse.ArgumentParser(prog="keeper.app")
    ap.add_argument("--host", default=s.APP_HOST)
    ap.add_argument("--port", type=int, default=s.APP_PORT)
    ap.add_argument("--reload", action="store_true")
    a = ap.parse_args()
    try:
        for w in validate_startup(s):
            print(f"! {w}", file=sys.stderr)
    except StartupError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 4
    uvicorn.run("keeper.app:create_app", factory=True, host=a.host, port=a.port, reload=a.reload,
                reload_dirs=[str(s.path("backend/keeper"))] if a.reload else None, log_level="warning",
                access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())

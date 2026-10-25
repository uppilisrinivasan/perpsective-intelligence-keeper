"""python -m keeper.db upgrade | revision -m "…" — Alembic wrapper that needs no working directory."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

HERE = Path(__file__).resolve().parent


def alembic_config() -> Config:
    cfg = Config(str(HERE.parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(HERE / "migrations"))
    return cfg


def upgrade() -> None:
    from keeper.config import get_settings
    get_settings().runtime_dir.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(), "head")


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "upgrade":
        upgrade()
        return 0
    if argv[0] == "revision":
        msg = argv[argv.index("-m") + 1] if "-m" in argv else "change"
        command.revision(alembic_config(), message=msg, autogenerate=True)
        return 0
    print("usage: python -m keeper.db [upgrade | revision -m MESSAGE]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

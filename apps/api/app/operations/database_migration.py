from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import settings
from app.db.alembic_compat import preflight_alembic_version_table


def _config() -> Config:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def run_preflight() -> None:
    config = _config()
    engine = create_engine(settings.DATABASE_URL)
    try:
        preflight_alembic_version_table(engine, ScriptDirectory.from_config(config))
    finally:
        engine.dispose()


def upgrade(revision: str = "head") -> None:
    config = _config()
    run_preflight()
    command.upgrade(config, revision)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    action = args[0] if args else "upgrade"
    if action == "preflight":
        run_preflight()
        return 0
    if action == "upgrade":
        upgrade(args[1] if len(args) > 1 else "head")
        return 0
    raise SystemExit(f"Unsupported migration action: {action}")


if __name__ == "__main__":
    raise SystemExit(main())

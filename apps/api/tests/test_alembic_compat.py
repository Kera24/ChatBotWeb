from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, text

from app.db import alembic_compat
from app.db.alembic_compat import (
    ALEMBIC_VERSION_COLUMN,
    ALEMBIC_VERSION_TABLE,
    MIN_ALEMBIC_VERSION_LENGTH,
    ensure_alembic_version_table_compatibility,
    preflight_alembic_version_table,
    required_version_length,
)


def alembic_config(database_url: str | None = None) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def version_length(engine) -> int | None:
    column = next(column for column in inspect(engine).get_columns(ALEMBIC_VERSION_TABLE) if column["name"] == ALEMBIC_VERSION_COLUMN)
    return getattr(column["type"], "length", None)


def create_version_table(engine, length: int) -> None:
    metadata = MetaData()
    Table(ALEMBIC_VERSION_TABLE, metadata, Column(ALEMBIC_VERSION_COLUMN, String(length), primary_key=True, nullable=False))
    metadata.create_all(engine)


def test_preflight_creates_fresh_alembic_version_table_with_wide_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    config = alembic_config()

    preflight_alembic_version_table(engine, ScriptDirectory.from_config(config))

    assert ALEMBIC_VERSION_TABLE in inspect(engine).get_table_names()
    assert version_length(engine) == MIN_ALEMBIC_VERSION_LENGTH


def test_existing_sqlite_short_version_table_is_safe_and_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'short.db'}")
    create_version_table(engine, 32)
    config = alembic_config()

    preflight_alembic_version_table(engine, ScriptDirectory.from_config(config))
    preflight_alembic_version_table(engine, ScriptDirectory.from_config(config))

    assert version_length(engine) == 32


def test_already_wide_version_table_is_unchanged(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'wide.db'}")
    create_version_table(engine, 255)
    config = alembic_config()

    preflight_alembic_version_table(engine, ScriptDirectory.from_config(config))

    assert version_length(engine) == 255


def test_postgresql_short_version_table_is_widened(monkeypatch) -> None:
    connection = Mock()
    connection.dialect.name = "postgresql"
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = [{"name": ALEMBIC_VERSION_COLUMN, "type": String(32)}]
    monkeypatch.setattr(alembic_compat, "inspect", lambda _connection: inspector)

    ensure_alembic_version_table_compatibility(connection, min_length=128)

    executed_sql = str(connection.execute.call_args.args[0])
    assert "ALTER TABLE alembic_version" in executed_sql
    assert "TYPE VARCHAR(128)" in executed_sql


def test_preflight_fails_clearly_when_column_cannot_hold_target_revision(monkeypatch) -> None:
    connection = Mock()
    connection.dialect.name = "mysql"
    inspector = Mock()
    inspector.has_table.return_value = True
    inspector.get_columns.return_value = [{"name": ALEMBIC_VERSION_COLUMN, "type": String(32)}]
    monkeypatch.setattr(alembic_compat, "inspect", lambda _connection: inspector)

    try:
        ensure_alembic_version_table_compatibility(connection, min_length=128)
    except RuntimeError as exc:
        assert "alembic_version.version_num is VARCHAR(32)" in str(exc)
        assert "automatic widening is not implemented for mysql" in str(exc)
    else:
        raise AssertionError("expected compatibility failure")


def test_alembic_upgrade_through_head_uses_wide_version_table(tmp_path: Path) -> None:
    database_path = tmp_path / "upgrade-head.db"
    config = alembic_config(f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    assert version_length(engine) == MIN_ALEMBIC_VERSION_LENGTH
    with engine.connect() as connection:
        current_revision = connection.execute(text(f"select {ALEMBIC_VERSION_COLUMN} from {ALEMBIC_VERSION_TABLE}")).scalar_one()
    assert current_revision == "0016_evaluation_framework"


def test_revision_history_is_linear_and_identifiers_are_preserved() -> None:
    script = ScriptDirectory.from_config(alembic_config())
    revisions = list(script.walk_revisions())

    assert script.get_heads() == ["0016_evaluation_framework"]
    assert required_version_length(script) >= len("0016_evaluation_framework")
    assert [revision.revision for revision in revisions][0] == "0016_evaluation_framework"
    for revision in revisions:
        down_revision = revision.down_revision
        assert not isinstance(down_revision, tuple)
    assert {revision.revision for revision in revisions} >= {
        "0011_widget_embed_preferences",
        "0014_assistant_scoping",
        "0015_billing_foundation",
    }

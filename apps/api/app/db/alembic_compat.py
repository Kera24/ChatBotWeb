from __future__ import annotations

from alembic.ddl.impl import DefaultImpl
from alembic.script import ScriptDirectory
from sqlalchemy import Column, Engine, MetaData, PrimaryKeyConstraint, String, Table, inspect, text
from sqlalchemy.engine import Connection

MIN_ALEMBIC_VERSION_LENGTH = 128
ALEMBIC_VERSION_TABLE = "alembic_version"
ALEMBIC_VERSION_COLUMN = "version_num"


def install_wide_alembic_version_table() -> None:
    if getattr(DefaultImpl.version_table_impl, "_chatbotweb_wide_version", False):
        return

    def version_table_impl(self, *, version_table: str, version_table_schema: str | None, version_table_pk: bool, **kw) -> Table:
        table = Table(
            version_table,
            MetaData(),
            Column(ALEMBIC_VERSION_COLUMN, String(MIN_ALEMBIC_VERSION_LENGTH), nullable=False),
            schema=version_table_schema,
        )
        if version_table_pk:
            table.append_constraint(PrimaryKeyConstraint(ALEMBIC_VERSION_COLUMN, name=f"{version_table}_pkc"))
        return table

    version_table_impl._chatbotweb_wide_version = True
    DefaultImpl.version_table_impl = version_table_impl


def target_revision_length(script: ScriptDirectory) -> int:
    heads = script.get_heads()
    revisions = [revision.revision for revision in script.walk_revisions() if revision.revision]
    values = [*heads, *revisions]
    return max((len(value) for value in values), default=MIN_ALEMBIC_VERSION_LENGTH)


def required_version_length(script: ScriptDirectory) -> int:
    return max(MIN_ALEMBIC_VERSION_LENGTH, target_revision_length(script))


def ensure_alembic_version_table_compatibility(connection: Connection, *, min_length: int = MIN_ALEMBIC_VERSION_LENGTH) -> None:
    inspector = inspect(connection)
    if not inspector.has_table(ALEMBIC_VERSION_TABLE):
        metadata = MetaData()
        Table(
            ALEMBIC_VERSION_TABLE,
            metadata,
            Column(ALEMBIC_VERSION_COLUMN, String(min_length), primary_key=True, nullable=False),
        )
        metadata.create_all(connection, tables=[metadata.tables[ALEMBIC_VERSION_TABLE]])
        return

    columns = {column["name"]: column for column in inspector.get_columns(ALEMBIC_VERSION_TABLE)}
    version_column = columns.get(ALEMBIC_VERSION_COLUMN)
    if version_column is None:
        raise RuntimeError(f"{ALEMBIC_VERSION_TABLE}.{ALEMBIC_VERSION_COLUMN} is missing.")

    current_length = getattr(version_column["type"], "length", None)
    if current_length is None or current_length >= min_length:
        return

    dialect_name = connection.dialect.name
    if dialect_name == "postgresql":
        connection.execute(
            text(
                f"ALTER TABLE {ALEMBIC_VERSION_TABLE} "
                f"ALTER COLUMN {ALEMBIC_VERSION_COLUMN} TYPE VARCHAR({min_length})"
            )
        )
        return

    if dialect_name == "sqlite":
        return

    raise RuntimeError(
        f"{ALEMBIC_VERSION_TABLE}.{ALEMBIC_VERSION_COLUMN} is VARCHAR({current_length}); "
        f"automatic widening is not implemented for {dialect_name}."
    )


def validate_alembic_version_capacity(connection: Connection, *, min_length: int) -> None:
    inspector = inspect(connection)
    if not inspector.has_table(ALEMBIC_VERSION_TABLE):
        return
    columns = {column["name"]: column for column in inspector.get_columns(ALEMBIC_VERSION_TABLE)}
    version_column = columns.get(ALEMBIC_VERSION_COLUMN)
    if version_column is None:
        raise RuntimeError(f"{ALEMBIC_VERSION_TABLE}.{ALEMBIC_VERSION_COLUMN} is missing.")
    current_length = getattr(version_column["type"], "length", None)
    if current_length is not None and current_length < min_length and connection.dialect.name != "sqlite":
        raise RuntimeError(
            f"{ALEMBIC_VERSION_TABLE}.{ALEMBIC_VERSION_COLUMN} is VARCHAR({current_length}), "
            f"but the target Alembic revision requires at least {min_length} characters."
        )


def preflight_alembic_version_table(engine: Engine, script: ScriptDirectory) -> None:
    min_length = required_version_length(script)
    install_wide_alembic_version_table()
    with engine.begin() as connection:
        ensure_alembic_version_table_compatibility(connection, min_length=min_length)
        validate_alembic_version_capacity(connection, min_length=min_length)

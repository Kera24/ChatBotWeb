from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args(settings.DATABASE_URL),
    pool_pre_ping=True,
)

if engine.dialect.name == "sqlite":
    # SQLite allows only one writer at a time; without a busy timeout, a
    # second connection (e.g. the evaluation engine's per-case shadow
    # session - see app.evaluation.shadow_session) attempting to write while
    # this connection holds the lock fails immediately with "database is
    # locked" instead of waiting briefly for the lock to clear. This only
    # ever applies to SQLite (local dev/test/evaluation) - PostgreSQL, the
    # real production database, is unaffected.
    @event.listens_for(engine, "connect")
    def _set_sqlite_busy_timeout(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA busy_timeout = 10000")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

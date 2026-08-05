"""An isolated database session for calling the real RAG orchestrator without
ever persisting the conversation/citation rows it writes.

`RAGOrchestrator.answer()` unconditionally inserts a ChatSession/ChatMessage
(and, on success, Citation) rows through whatever `Session` it is given -
that's how the real dashboard/widget traffic works, and evaluation runs
reuse that exact code path on purpose (see app.evaluation.engine) rather than
duplicating RAG logic. To keep evaluation traffic out of real conversation
history, analytics, and the review queue "by default", every case in a run
executes against a session bound to its own connection + outer transaction
that is always rolled back afterwards, regardless of how many times the
orchestrator's repository calls commit internally.

This is a separate engine from `app.db.session.engine` - the shared
application engine used for real user traffic is never touched, so this
module cannot affect ordinary request handling even if something here were
misconfigured.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _build_shadow_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, connect_args=_connect_args(database_url), pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # pysqlite manages its own implicit transactions in a way that fights
        # SAVEPOINT-based nested transactions; this is SQLAlchemy's documented
        # workaround and only affects connections made through this dedicated
        # engine, never the shared application engine.
        @event.listens_for(engine, "connect")
        def _disable_pysqlite_implicit_transactions(dbapi_connection, _connection_record) -> None:
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def _start_explicit_transaction(connection) -> None:
            connection.exec_driver_sql("BEGIN")

    return engine


@contextmanager
def shadow_rag_session(database_url: str | None = None) -> Iterator[Session]:
    """Yield a Session whose writes are guaranteed to be rolled back on exit,
    even though the code using it (the real RAGOrchestrator) calls
    `session.commit()` internally one or more times."""
    engine = _build_shadow_engine(database_url or settings.DATABASE_URL)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
        engine.dispose()

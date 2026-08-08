from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.observability.ai_trace_recorder import AITraceRecorder, NoOpAITraceRecorder, SqlAlchemyAITraceRecorder


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_ai_trace_recorder(db: Session) -> AITraceRecorder:
    """Builds a recorder whose short-lived write sessions are bound to the
    SAME engine as the caller's request-scoped `db` session (via
    `db.get_bind()`), rather than the global `app.db.session.SessionLocal`.
    This matters in tests: `app.dependency_overrides[get_db]` points at a
    throwaway in-memory SQLite engine that is NOT the same engine
    `SessionLocal` is bound to at import time, so hard-coding `SessionLocal`
    here would silently write trace rows to a different database than the
    one the test (or production request) actually uses.

    Safe for every single-threaded call site (the authenticated dashboard-test
    endpoint and the public widget endpoint both use one session on one
    thread per request). NOT safe to use as-is for a caller that writes from
    a different thread than the one holding a long-lived `db` - see
    app.evaluation.engine.build_evaluation_trace_recorder, which guards that
    specific scenario separately.
    """
    if not _truthy(settings.AI_TRACE_ENABLED):
        return NoOpAITraceRecorder()
    session_factory = sessionmaker(bind=db.get_bind())
    return SqlAlchemyAITraceRecorder(session_factory=session_factory)


def get_ai_trace_recorder(db: Session) -> AITraceRecorder:
    """FastAPI dependency form of build_ai_trace_recorder, for routes that
    want to construct a RAGOrchestrator with tracing wired in."""
    return build_ai_trace_recorder(db)

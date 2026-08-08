from __future__ import annotations

from unittest.mock import MagicMock

from app.evaluation.engine import _build_evaluation_trace_recorder
from app.observability.ai_trace_recorder import NoOpAITraceRecorder, SqlAlchemyAITraceRecorder


def _fake_session(dialect_name: str) -> MagicMock:
    session = MagicMock()
    session.get_bind.return_value.dialect.name = dialect_name
    return session


def test_evaluation_trace_recorder_is_noop_on_sqlite() -> None:
    """SQLite's single-writer file locking makes a cross-thread trace-write
    (from app.evaluation.engine's ThreadPoolExecutor worker) contend with the
    evaluation engine's own long-lived session badly enough to risk
    surfacing "database is locked" errors on the PRIMARY evaluation write
    path too - reproduced directly during development of this feature. The
    engine must fall back to a no-op recorder on SQLite specifically, so
    evaluation runs are never destabilised by AI trace recording. See
    app.evaluation.engine._build_evaluation_trace_recorder's docstring and
    docs/03_AI/AI_Observability_Architecture.md's limitations section."""
    recorder = _build_evaluation_trace_recorder(_fake_session("sqlite"))
    assert isinstance(recorder, NoOpAITraceRecorder)


def test_evaluation_trace_recorder_is_real_on_postgres() -> None:
    """On Postgres (the real production dialect, proper MVCC, no
    single-writer file lock) evaluation-triggered RAG calls ARE traced and
    tagged with eval_run_id/eval_case_id."""
    recorder = _build_evaluation_trace_recorder(_fake_session("postgresql"))
    assert isinstance(recorder, SqlAlchemyAITraceRecorder)

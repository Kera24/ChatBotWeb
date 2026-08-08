from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AIRetrievalTrace, AITrace, AITraceStage

DEFAULT_BATCH_SIZE = 500


@dataclass(frozen=True)
class RetentionCleanupResult:
    cutoff: datetime
    traces_deleted: int
    stages_deleted: int
    retrieval_deleted: int
    model_calls_deleted: int
    guardrails_deleted: int


def cleanup_expired_traces(db: Session, *, retention_days: int, now: datetime | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> RetentionCleanupResult:
    """Deletes AI trace rows (and their child stage/retrieval/model-call/
    guardrail rows) older than `retention_days`. Deletes child tables first,
    then `ai_traces`, explicitly (no ON DELETE CASCADE relied upon - explicit
    is safer than implicit for a data-retention feature, and keeps this
    portable across SQLite/Postgres). Batched to avoid long-held locks on a
    production Postgres database with a large backlog.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    stages_deleted = 0
    retrieval_deleted = 0
    model_calls_deleted = 0
    guardrails_deleted = 0
    traces_deleted = 0

    while True:
        batch_trace_ids = list(
            db.execute(select(AITrace.id).where(AITrace.created_at < cutoff).limit(batch_size)).scalars().all()
        )
        if not batch_trace_ids:
            break

        stages_deleted += db.execute(delete(AITraceStage).where(AITraceStage.trace_id.in_(batch_trace_ids))).rowcount or 0
        retrieval_deleted += db.execute(delete(AIRetrievalTrace).where(AIRetrievalTrace.trace_id.in_(batch_trace_ids))).rowcount or 0
        model_calls_deleted += db.execute(delete(AIModelCallTrace).where(AIModelCallTrace.trace_id.in_(batch_trace_ids))).rowcount or 0
        guardrails_deleted += db.execute(delete(AIGuardrailTrace).where(AIGuardrailTrace.trace_id.in_(batch_trace_ids))).rowcount or 0
        traces_deleted += db.execute(delete(AITrace).where(AITrace.id.in_(batch_trace_ids))).rowcount or 0
        db.commit()

    return RetentionCleanupResult(
        cutoff=cutoff, traces_deleted=traces_deleted, stages_deleted=stages_deleted,
        retrieval_deleted=retrieval_deleted, model_calls_deleted=model_calls_deleted, guardrails_deleted=guardrails_deleted,
    )

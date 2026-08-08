from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AIRetrievalTrace, AITrace, AITraceStage
from app.observability.retention import cleanup_expired_traces


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db) -> tuple[str, str]:
    organisation = Organisation(name="Org", slug="org-retention")
    workspace = Workspace(organisation=organisation, name="WS", slug="ws-retention")
    user = User(email="owner@example.test")
    membership = Membership(organisation=organisation, user=user, role="org_owner")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation.id, workspace.id


def _seed_trace(db, *, organisation_id: str, workspace_id: str, created_at: datetime, trace_id: str) -> str:
    trace = AITrace(
        trace_id=trace_id, organisation_id=organisation_id, workspace_id=workspace_id, channel="dashboard_test",
        status="completed", answer_state="answered", fallback_used=False, created_at=created_at,
    )
    db.add(trace)
    db.flush()
    db.add(AITraceStage(trace_id=trace.id, organisation_id=organisation_id, workspace_id=workspace_id, stage_name="request_accepted", sequence_number=1, status="ok", created_at=created_at))
    db.add(AIRetrievalTrace(trace_id=trace.id, organisation_id=organisation_id, workspace_id=workspace_id, rank=1, selected=True, created_at=created_at))
    db.add(AIModelCallTrace(trace_id=trace.id, organisation_id=organisation_id, workspace_id=workspace_id, outcome="success", created_at=created_at))
    db.add(AIGuardrailTrace(trace_id=trace.id, organisation_id=organisation_id, workspace_id=workspace_id, layer="C+D", guardrail_name="input_policy", verdict="passed", blocked=False, created_at=created_at))
    db.commit()
    return trace.id


def test_cleanup_deletes_only_traces_older_than_retention_window(db_session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session)
    now = datetime.now(timezone.utc)
    old_trace_id = _seed_trace(db_session, organisation_id=organisation_id, workspace_id=workspace_id, created_at=now - timedelta(days=100), trace_id="trc_old")
    recent_trace_id = _seed_trace(db_session, organisation_id=organisation_id, workspace_id=workspace_id, created_at=now - timedelta(days=1), trace_id="trc_recent")

    result = cleanup_expired_traces(db_session, retention_days=90, now=now)

    assert result.traces_deleted == 1
    assert result.stages_deleted == 1
    assert result.retrieval_deleted == 1
    assert result.model_calls_deleted == 1
    assert result.guardrails_deleted == 1

    remaining_trace_ids = set(db_session.execute(select(AITrace.id)).scalars().all())
    assert remaining_trace_ids == {recent_trace_id}
    assert db_session.execute(select(AITraceStage).where(AITraceStage.trace_id == old_trace_id)).first() is None
    assert db_session.execute(select(AIRetrievalTrace).where(AIRetrievalTrace.trace_id == old_trace_id)).first() is None
    assert db_session.execute(select(AIModelCallTrace).where(AIModelCallTrace.trace_id == old_trace_id)).first() is None
    assert db_session.execute(select(AIGuardrailTrace).where(AIGuardrailTrace.trace_id == old_trace_id)).first() is None


def test_cleanup_is_a_no_op_when_nothing_is_expired(db_session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session)
    now = datetime.now(timezone.utc)
    _seed_trace(db_session, organisation_id=organisation_id, workspace_id=workspace_id, created_at=now - timedelta(days=1), trace_id="trc_recent")

    result = cleanup_expired_traces(db_session, retention_days=90, now=now)

    assert result.traces_deleted == 0
    assert db_session.execute(select(AITrace)).first() is not None


def test_cleanup_batches_across_multiple_iterations(db_session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session)
    now = datetime.now(timezone.utc)
    for index in range(12):
        _seed_trace(db_session, organisation_id=organisation_id, workspace_id=workspace_id, created_at=now - timedelta(days=100), trace_id=f"trc_old_{index}")

    result = cleanup_expired_traces(db_session, retention_days=90, now=now, batch_size=5)

    assert result.traces_deleted == 12
    assert db_session.execute(select(AITrace)).first() is None

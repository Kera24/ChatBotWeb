from sqlalchemy import select

from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AITrace, AITraceStage
from test_public_widget_message_endpoint import add_embedded_chunk_for_public_key, client, create_public_session, post_message
from test_public_widget_session_endpoint import seed_widget


def test_public_widget_message_produces_an_ai_trace_tagged_with_widget_channel(client) -> None:  # noqa: ANN001
    """The public widget path shares the same RAGOrchestrator as the
    authenticated dashboard-test path (see app.access.messages.rag_adapter),
    so it must produce the same shape of AI trace - just tagged with
    channel="widget" instead of "dashboard_test", and never exposing
    trace_id in the public-facing response body (see
    docs/03_AI/AI_Observability_Architecture.md's correlation-model section)."""
    public_key = seed_widget(client)
    add_embedded_chunk_for_public_key(client, public_key, content="applications close in december", title="Admissions Handbook")
    token = create_public_session(client, public_key)

    response = post_message(client, public_key, token, message="applications close in december", key="idem-parity-123456")

    assert response.status_code == 200, response.text
    body = response.json()
    # trace_id is an internal correlation id - never surfaced in the public,
    # unauthenticated response body (it never identifies the tenant, but the
    # public contract deliberately stays minimal - see rag_adapter.py).
    assert "trace_id" not in body

    with client.app.state.testing_session() as db:
        traces = db.execute(select(AITrace).where(AITrace.channel == "widget")).scalars().all()
        assert len(traces) == 1
        trace = traces[0]
        assert trace.status == "completed"
        assert trace.answer_state == "answered"
        assert trace.fallback_used is False

        stages = db.execute(select(AITraceStage).where(AITraceStage.trace_id == trace.id)).scalars().all()
        stage_names = {stage.stage_name for stage in stages}
        # Same stage taxonomy as the authenticated path (see
        # test_ai_trace_recording.py::test_answered_request_produces_a_complete_trace).
        for expected_stage in ("request_accepted", "input_policy", "retrieval", "evidence_sufficiency", "provider_generation", "output_sanitisation", "persistence", "response_completed"):
            assert expected_stage in stage_names

        guardrails = db.execute(select(AIGuardrailTrace).where(AIGuardrailTrace.trace_id == trace.id)).scalars().all()
        assert len(guardrails) > 0
        assert all(g.blocked is False for g in guardrails)

        model_calls = db.execute(select(AIModelCallTrace).where(AIModelCallTrace.trace_id == trace.id)).scalars().all()
        assert len(model_calls) == 1
        assert model_calls[0].outcome == "success"

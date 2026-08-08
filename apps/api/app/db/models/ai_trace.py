from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Numeric

from app.db.base import Base, UUIDPrimaryKeyMixin


class AITrace(UUIDPrimaryKeyMixin, Base):
    """Root row for one end-to-end AI request (dashboard test, public widget
    message, or evaluation case). See app.observability.ai_trace_recorder for
    the fail-safe writer and app.observability.context.AITraceContext for the
    trace_id/request_id/eval_run_id correlation model."""

    __tablename__ = "ai_traces"
    __table_args__ = (
        Index("ix_ai_traces_trace_id", "trace_id", unique=True),
        Index("ix_ai_traces_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_ai_traces_assistant", "organisation_id", "workspace_id", "assistant_id"),
        Index("ix_ai_traces_conversation", "conversation_id"),
        Index("ix_ai_traces_created_at", "created_at"),
        Index("ix_ai_traces_status_answer_state", "organisation_id", "workspace_id", "status", "answer_state"),
        Index("ix_ai_traces_eval_run", "eval_run_id"),
    )

    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    assistant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("widgets.id"), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    otel_trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    otel_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eval_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_runs.id"), nullable=True, index=True)
    eval_case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("evaluation_cases.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", server_default="in_progress")
    answer_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD", server_default="USD")
    content_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="metadata_only", server_default="metadata_only")
    error_class: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class AITraceStage(UUIDPrimaryKeyMixin, Base):
    """One row per pipeline stage within a trace - see
    app.observability.context.ALL_STAGES for the fixed stage-name taxonomy."""

    __tablename__ = "ai_trace_stages"
    __table_args__ = (
        Index("ix_ai_trace_stages_trace", "trace_id", "sequence_number"),
        Index("ix_ai_trace_stages_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_ai_trace_stages_stage_status", "stage_name", "status"),
    )

    trace_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_traces.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    stage_name: Mapped[str] = mapped_column(String(60), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_class: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_counts_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider_model_config_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class AIRetrievalTrace(UUIDPrimaryKeyMixin, Base):
    """One row per candidate chunk considered during retrieval, selected or
    rejected. `content_preview` is only ever populated when the trace's
    content_mode is not metadata_only, and always passes through
    app.observability.redaction first."""

    __tablename__ = "ai_retrieval_traces"
    __table_args__ = (
        Index("ix_ai_retrieval_traces_trace", "trace_id"),
        Index("ix_ai_retrieval_traces_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_ai_retrieval_traces_chunk", "chunk_id"),
    )

    trace_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_traces.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    chunk_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chunks.id"), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    rejection_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class AIModelCallTrace(UUIDPrimaryKeyMixin, Base):
    """One row per provider generation call (usually 1:1 with a trace; the
    attempt_number column allows for future retries without a schema
    change)."""

    __tablename__ = "ai_model_call_traces"
    __table_args__ = (
        Index("ix_ai_model_call_traces_trace", "trace_id"),
        Index("ix_ai_model_call_traces_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_ai_model_call_traces_provider_model", "provider_key", "model_key", "created_at"),
    )

    trace_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_traces.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    provider_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_input_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    estimated_output_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    estimated_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD", server_default="USD")
    cost_calc_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pricing_known: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_prompt_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured prompt-version-management identity (see
    # app.prompts.resolution) - prompt_version_id is the platform_core
    # layer's resolved PromptVersion id (a quick-filter FK); the full
    # per-layer picture lives in resolved_layer_version_ids, since a
    # composite render can span multiple independently-versioned layers and
    # no single scalar column can represent that.
    prompt_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prompt_versions.id"), nullable=True, index=True)
    experiment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("prompt_experiments.id"), nullable=True, index=True)
    experiment_arm: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_layer_version_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class AIGuardrailTrace(UUIDPrimaryKeyMixin, Base):
    """One row per guardrail layer evaluated (A-H, see the inline comments in
    app.ai.rag_orchestrator.RAGOrchestrator.answer for the layer taxonomy)."""

    __tablename__ = "ai_guardrail_traces"
    __table_args__ = (
        Index("ix_ai_guardrail_traces_trace", "trace_id"),
        Index("ix_ai_guardrail_traces_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_ai_guardrail_traces_guardrail_reason", "guardrail_name", "reason_code", "created_at"),
    )

    trace_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_traces.id"), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    guardrail_name: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    reason_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

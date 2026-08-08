"""add AI observability trace tables

Revision ID: 0017_ai_observability
Revises: 0016_evaluation_framework
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0017_ai_observability"
down_revision: str | None = "0016_evaluation_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.create_table(
        "ai_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_id", sa.String(length=36), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("otel_trace_id", sa.String(length=32), nullable=True),
        sa.Column("otel_span_id", sa.String(length=16), nullable=True),
        sa.Column("eval_run_id", sa.String(length=36), nullable=True),
        sa.Column("eval_case_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("answer_state", sa.String(length=40), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column("provider_key", sa.String(length=120), nullable=True),
        sa.Column("model_key", sa.String(length=120), nullable=True),
        sa.Column("provider_model_name", sa.String(length=160), nullable=True),
        sa.Column("embedding_provider", sa.String(length=120), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("cost_currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("content_mode", sa.String(length=20), nullable=False, server_default="metadata_only"),
        sa.Column("error_class", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_traces_organisation_id", "ai_traces", ["organisation_id"])
    op.create_index("ix_ai_traces_workspace_id", "ai_traces", ["workspace_id"])
    op.create_index("ix_ai_traces_assistant_id", "ai_traces", ["assistant_id"])
    op.create_index("ix_ai_traces_conversation_id", "ai_traces", ["conversation_id"])
    op.create_index("ix_ai_traces_eval_run_id", "ai_traces", ["eval_run_id"])
    op.create_index("ix_ai_traces_eval_case_id", "ai_traces", ["eval_case_id"])
    op.create_index("ix_ai_traces_trace_id", "ai_traces", ["trace_id"], unique=True)
    op.create_index("ix_ai_traces_tenant_workspace", "ai_traces", ["organisation_id", "workspace_id"])
    op.create_index("ix_ai_traces_assistant", "ai_traces", ["organisation_id", "workspace_id", "assistant_id"])
    op.create_index("ix_ai_traces_conversation", "ai_traces", ["conversation_id"])
    op.create_index("ix_ai_traces_created_at", "ai_traces", ["created_at"])
    op.create_index("ix_ai_traces_status_answer_state", "ai_traces", ["organisation_id", "workspace_id", "status", "answer_state"])
    op.create_index("ix_ai_traces_eval_run", "ai_traces", ["eval_run_id"])

    op.create_table(
        "ai_trace_stages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("stage_name", sa.String(length=60), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("error_class", sa.String(length=80), nullable=True),
        sa.Column("safe_counts_json", sa.JSON(), nullable=True),
        sa.Column("provider_model_config_version", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_trace_stages_trace_id", "ai_trace_stages", ["trace_id"])
    op.create_index("ix_ai_trace_stages_organisation_id", "ai_trace_stages", ["organisation_id"])
    op.create_index("ix_ai_trace_stages_workspace_id", "ai_trace_stages", ["workspace_id"])
    op.create_index("ix_ai_trace_stages_trace", "ai_trace_stages", ["trace_id", "sequence_number"])
    op.create_index("ix_ai_trace_stages_tenant_workspace", "ai_trace_stages", ["organisation_id", "workspace_id"])
    op.create_index("ix_ai_trace_stages_stage_status", "ai_trace_stages", ["stage_name", "status"])

    op.create_table(
        "ai_retrieval_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("rejection_reason", sa.String(length=80), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_retrieval_traces_trace_id", "ai_retrieval_traces", ["trace_id"])
    op.create_index("ix_ai_retrieval_traces_organisation_id", "ai_retrieval_traces", ["organisation_id"])
    op.create_index("ix_ai_retrieval_traces_workspace_id", "ai_retrieval_traces", ["workspace_id"])
    op.create_index("ix_ai_retrieval_traces_chunk_id", "ai_retrieval_traces", ["chunk_id"])
    op.create_index("ix_ai_retrieval_traces_document_id", "ai_retrieval_traces", ["document_id"])
    op.create_index("ix_ai_retrieval_traces_trace", "ai_retrieval_traces", ["trace_id"])
    op.create_index("ix_ai_retrieval_traces_tenant_workspace", "ai_retrieval_traces", ["organisation_id", "workspace_id"])
    op.create_index("ix_ai_retrieval_traces_chunk", "ai_retrieval_traces", ["chunk_id"])

    op.create_table(
        "ai_model_call_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider_key", sa.String(length=120), nullable=True),
        sa.Column("model_key", sa.String(length=120), nullable=True),
        sa.Column("provider_model_name", sa.String(length=160), nullable=True),
        sa.Column("prompt_key", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("prompt_hash", sa.String(length=128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_input_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("estimated_output_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("estimated_total_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("cost_currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("cost_calc_version", sa.String(length=40), nullable=True),
        sa.Column("pricing_known", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(length=80), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("raw_prompt_preview", sa.Text(), nullable=True),
        sa.Column("raw_response_preview", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_model_call_traces_trace_id", "ai_model_call_traces", ["trace_id"])
    op.create_index("ix_ai_model_call_traces_organisation_id", "ai_model_call_traces", ["organisation_id"])
    op.create_index("ix_ai_model_call_traces_workspace_id", "ai_model_call_traces", ["workspace_id"])
    op.create_index("ix_ai_model_call_traces_trace", "ai_model_call_traces", ["trace_id"])
    op.create_index("ix_ai_model_call_traces_tenant_workspace", "ai_model_call_traces", ["organisation_id", "workspace_id"])
    op.create_index("ix_ai_model_call_traces_provider_model", "ai_model_call_traces", ["provider_key", "model_key", "created_at"])

    op.create_table(
        "ai_guardrail_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("layer", sa.String(length=20), nullable=False),
        sa.Column("guardrail_name", sa.String(length=80), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("safe_detail_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_guardrail_traces_trace_id", "ai_guardrail_traces", ["trace_id"])
    op.create_index("ix_ai_guardrail_traces_organisation_id", "ai_guardrail_traces", ["organisation_id"])
    op.create_index("ix_ai_guardrail_traces_workspace_id", "ai_guardrail_traces", ["workspace_id"])
    op.create_index("ix_ai_guardrail_traces_trace", "ai_guardrail_traces", ["trace_id"])
    op.create_index("ix_ai_guardrail_traces_tenant_workspace", "ai_guardrail_traces", ["organisation_id", "workspace_id"])
    op.create_index("ix_ai_guardrail_traces_guardrail_reason", "ai_guardrail_traces", ["guardrail_name", "reason_code", "created_at"])

    if dialect != "sqlite":
        op.create_foreign_key("fk_ai_traces_organisation_id_organisations", "ai_traces", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_ai_traces_workspace_id_workspaces", "ai_traces", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_ai_traces_assistant_id_widgets", "ai_traces", "widgets", ["assistant_id"], ["id"])
        op.create_foreign_key("fk_ai_traces_conversation_id_chat_sessions", "ai_traces", "chat_sessions", ["conversation_id"], ["id"])
        op.create_foreign_key("fk_ai_traces_eval_run_id_evaluation_runs", "ai_traces", "evaluation_runs", ["eval_run_id"], ["id"])
        op.create_foreign_key("fk_ai_traces_eval_case_id_evaluation_cases", "ai_traces", "evaluation_cases", ["eval_case_id"], ["id"])

        op.create_foreign_key("fk_ai_trace_stages_trace_id_ai_traces", "ai_trace_stages", "ai_traces", ["trace_id"], ["id"])
        op.create_foreign_key("fk_ai_trace_stages_organisation_id_organisations", "ai_trace_stages", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_ai_trace_stages_workspace_id_workspaces", "ai_trace_stages", "workspaces", ["workspace_id"], ["id"])

        op.create_foreign_key("fk_ai_retrieval_traces_trace_id_ai_traces", "ai_retrieval_traces", "ai_traces", ["trace_id"], ["id"])
        op.create_foreign_key("fk_ai_retrieval_traces_organisation_id_organisations", "ai_retrieval_traces", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_ai_retrieval_traces_workspace_id_workspaces", "ai_retrieval_traces", "workspaces", ["workspace_id"], ["id"])
        op.create_foreign_key("fk_ai_retrieval_traces_chunk_id_chunks", "ai_retrieval_traces", "chunks", ["chunk_id"], ["id"])
        op.create_foreign_key("fk_ai_retrieval_traces_document_id_documents", "ai_retrieval_traces", "documents", ["document_id"], ["id"])

        op.create_foreign_key("fk_ai_model_call_traces_trace_id_ai_traces", "ai_model_call_traces", "ai_traces", ["trace_id"], ["id"])
        op.create_foreign_key("fk_ai_model_call_traces_organisation_id_organisations", "ai_model_call_traces", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_ai_model_call_traces_workspace_id_workspaces", "ai_model_call_traces", "workspaces", ["workspace_id"], ["id"])

        op.create_foreign_key("fk_ai_guardrail_traces_trace_id_ai_traces", "ai_guardrail_traces", "ai_traces", ["trace_id"], ["id"])
        op.create_foreign_key("fk_ai_guardrail_traces_organisation_id_organisations", "ai_guardrail_traces", "organisations", ["organisation_id"], ["id"])
        op.create_foreign_key("fk_ai_guardrail_traces_workspace_id_workspaces", "ai_guardrail_traces", "workspaces", ["workspace_id"], ["id"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "sqlite":
        op.drop_constraint("fk_ai_guardrail_traces_workspace_id_workspaces", "ai_guardrail_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_guardrail_traces_organisation_id_organisations", "ai_guardrail_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_guardrail_traces_trace_id_ai_traces", "ai_guardrail_traces", type_="foreignkey")

        op.drop_constraint("fk_ai_model_call_traces_workspace_id_workspaces", "ai_model_call_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_model_call_traces_organisation_id_organisations", "ai_model_call_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_model_call_traces_trace_id_ai_traces", "ai_model_call_traces", type_="foreignkey")

        op.drop_constraint("fk_ai_retrieval_traces_document_id_documents", "ai_retrieval_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_retrieval_traces_chunk_id_chunks", "ai_retrieval_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_retrieval_traces_workspace_id_workspaces", "ai_retrieval_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_retrieval_traces_organisation_id_organisations", "ai_retrieval_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_retrieval_traces_trace_id_ai_traces", "ai_retrieval_traces", type_="foreignkey")

        op.drop_constraint("fk_ai_trace_stages_workspace_id_workspaces", "ai_trace_stages", type_="foreignkey")
        op.drop_constraint("fk_ai_trace_stages_organisation_id_organisations", "ai_trace_stages", type_="foreignkey")
        op.drop_constraint("fk_ai_trace_stages_trace_id_ai_traces", "ai_trace_stages", type_="foreignkey")

        op.drop_constraint("fk_ai_traces_eval_case_id_evaluation_cases", "ai_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_traces_eval_run_id_evaluation_runs", "ai_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_traces_conversation_id_chat_sessions", "ai_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_traces_assistant_id_widgets", "ai_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_traces_workspace_id_workspaces", "ai_traces", type_="foreignkey")
        op.drop_constraint("fk_ai_traces_organisation_id_organisations", "ai_traces", type_="foreignkey")

    op.drop_index("ix_ai_guardrail_traces_guardrail_reason", table_name="ai_guardrail_traces")
    op.drop_index("ix_ai_guardrail_traces_tenant_workspace", table_name="ai_guardrail_traces")
    op.drop_index("ix_ai_guardrail_traces_trace", table_name="ai_guardrail_traces")
    op.drop_index("ix_ai_guardrail_traces_workspace_id", table_name="ai_guardrail_traces")
    op.drop_index("ix_ai_guardrail_traces_organisation_id", table_name="ai_guardrail_traces")
    op.drop_index("ix_ai_guardrail_traces_trace_id", table_name="ai_guardrail_traces")
    op.drop_table("ai_guardrail_traces")

    op.drop_index("ix_ai_model_call_traces_provider_model", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_tenant_workspace", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_trace", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_workspace_id", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_organisation_id", table_name="ai_model_call_traces")
    op.drop_index("ix_ai_model_call_traces_trace_id", table_name="ai_model_call_traces")
    op.drop_table("ai_model_call_traces")

    op.drop_index("ix_ai_retrieval_traces_chunk", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_tenant_workspace", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_trace", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_document_id", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_chunk_id", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_workspace_id", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_organisation_id", table_name="ai_retrieval_traces")
    op.drop_index("ix_ai_retrieval_traces_trace_id", table_name="ai_retrieval_traces")
    op.drop_table("ai_retrieval_traces")

    op.drop_index("ix_ai_trace_stages_stage_status", table_name="ai_trace_stages")
    op.drop_index("ix_ai_trace_stages_tenant_workspace", table_name="ai_trace_stages")
    op.drop_index("ix_ai_trace_stages_trace", table_name="ai_trace_stages")
    op.drop_index("ix_ai_trace_stages_workspace_id", table_name="ai_trace_stages")
    op.drop_index("ix_ai_trace_stages_organisation_id", table_name="ai_trace_stages")
    op.drop_index("ix_ai_trace_stages_trace_id", table_name="ai_trace_stages")
    op.drop_table("ai_trace_stages")

    op.drop_index("ix_ai_traces_eval_run", table_name="ai_traces")
    op.drop_index("ix_ai_traces_status_answer_state", table_name="ai_traces")
    op.drop_index("ix_ai_traces_created_at", table_name="ai_traces")
    op.drop_index("ix_ai_traces_conversation", table_name="ai_traces")
    op.drop_index("ix_ai_traces_assistant", table_name="ai_traces")
    op.drop_index("ix_ai_traces_tenant_workspace", table_name="ai_traces")
    op.drop_index("ix_ai_traces_trace_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_eval_case_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_eval_run_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_conversation_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_assistant_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_workspace_id", table_name="ai_traces")
    op.drop_index("ix_ai_traces_organisation_id", table_name="ai_traces")
    op.drop_table("ai_traces")

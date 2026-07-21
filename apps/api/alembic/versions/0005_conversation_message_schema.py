"""create conversation message schema

Revision ID: 0005_conversation_schema
Revises: 0004_audit_events
Create Date: 2026-07-12
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_conversation_schema"
down_revision: str | None = "0004_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("anonymous_user_id", sa.String(length=120), nullable=True),
        sa.Column("external_user_id", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_organisation_id", "chat_sessions", ["organisation_id"])
    op.create_index("ix_chat_sessions_workspace_id", "chat_sessions", ["workspace_id"])
    op.create_index("ix_chat_sessions_tenant_workspace", "chat_sessions", ["organisation_id", "workspace_id"])
    op.create_index("ix_chat_sessions_tenant_status", "chat_sessions", ["organisation_id", "workspace_id", "status"])
    op.create_index("ix_chat_sessions_recent", "chat_sessions", ["organisation_id", "workspace_id", "last_message_at", "started_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("answer_state", sa.String(length=40), nullable=True),
        sa.Column("model_key", sa.String(length=120), nullable=True),
        sa.Column("provider_key", sa.String(length=120), nullable=True),
        sa.Column("provider_model_name", sa.String(length=160), nullable=True),
        sa.Column("prompt_key", sa.String(length=160), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("prompt_hash", sa.String(length=128), nullable=True),
        sa.Column("execution_id", sa.String(length=80), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 8), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(length=80), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_sessions.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence_number", name="uq_chat_messages_conversation_sequence"),
    )
    op.create_index("ix_chat_messages_organisation_id", "chat_messages", ["organisation_id"])
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"])
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_tenant_workspace", "chat_messages", ["organisation_id", "workspace_id"])
    op.create_index("ix_chat_messages_conversation_order", "chat_messages", ["conversation_id", "sequence_number"])
    op.create_index("ix_chat_messages_execution_id", "chat_messages", ["execution_id"])

    op.create_table(
        "citations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("citation_index", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(8, 6), nullable=True),
        sa.Column("source_title", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=512), nullable=True),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_sessions.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "citation_index", name="uq_citations_message_index"),
    )
    op.create_index("ix_citations_organisation_id", "citations", ["organisation_id"])
    op.create_index("ix_citations_workspace_id", "citations", ["workspace_id"])
    op.create_index("ix_citations_conversation_id", "citations", ["conversation_id"])
    op.create_index("ix_citations_message_id", "citations", ["message_id"])
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])
    op.create_index("ix_citations_document_id", "citations", ["document_id"])
    op.create_index("ix_citations_document_version_id", "citations", ["document_version_id"])
    op.create_index("ix_citations_tenant_workspace", "citations", ["organisation_id", "workspace_id"])
    op.create_index("ix_citations_message_order", "citations", ["message_id", "citation_index"])
    op.create_index("ix_citations_chunk", "citations", ["chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_citations_chunk", table_name="citations")
    op.drop_index("ix_citations_message_order", table_name="citations")
    op.drop_index("ix_citations_tenant_workspace", table_name="citations")
    op.drop_index("ix_citations_document_version_id", table_name="citations")
    op.drop_index("ix_citations_document_id", table_name="citations")
    op.drop_index("ix_citations_chunk_id", table_name="citations")
    op.drop_index("ix_citations_message_id", table_name="citations")
    op.drop_index("ix_citations_conversation_id", table_name="citations")
    op.drop_index("ix_citations_workspace_id", table_name="citations")
    op.drop_index("ix_citations_organisation_id", table_name="citations")
    op.drop_table("citations")
    op.drop_index("ix_chat_messages_execution_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_order", table_name="chat_messages")
    op.drop_index("ix_chat_messages_tenant_workspace", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_workspace_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_organisation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_recent", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_tenant_status", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_tenant_workspace", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_workspace_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_organisation_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

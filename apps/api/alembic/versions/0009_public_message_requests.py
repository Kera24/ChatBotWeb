"""create public message requests

Revision ID: 0009_public_messages
Revises: 0008_public_sessions
Create Date: 2026-07-15
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_public_messages"
down_revision: str | None = "0008_public_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_message_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("credential_id", sa.String(length=36), nullable=False),
        sa.Column("public_session_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="received", nullable=False),
        sa.Column("user_message_id", sa.String(length=36), nullable=True),
        sa.Column("assistant_message_id", sa.String(length=36), nullable=True),
        sa.Column("response_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('received', 'processing', 'completed', 'failed')", name="ck_public_message_requests_status"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["public_session_id"], ["public_sessions.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_session_id", "idempotency_key_hash", name="uq_public_message_requests_session_key"),
    )
    op.create_index("ix_public_message_requests_tenant_workspace", "public_message_requests", ["organisation_id", "workspace_id"])
    op.create_index("ix_public_message_requests_credential", "public_message_requests", ["credential_id"])
    op.create_index("ix_public_message_requests_session", "public_message_requests", ["public_session_id"])
    op.create_index("ix_public_message_requests_status", "public_message_requests", ["status"])
    op.create_index("ix_public_message_requests_expires_at", "public_message_requests", ["expires_at"])
    op.create_index("ix_public_message_requests_deleted_at", "public_message_requests", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_public_message_requests_deleted_at", table_name="public_message_requests")
    op.drop_index("ix_public_message_requests_expires_at", table_name="public_message_requests")
    op.drop_index("ix_public_message_requests_status", table_name="public_message_requests")
    op.drop_index("ix_public_message_requests_session", table_name="public_message_requests")
    op.drop_index("ix_public_message_requests_credential", table_name="public_message_requests")
    op.drop_index("ix_public_message_requests_tenant_workspace", table_name="public_message_requests")
    op.drop_table("public_message_requests")

"""create public sessions

Revision ID: 0008_public_sessions
Revises: 0007_public_access_config
Create Date: 2026-07-15
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_public_sessions"
down_revision: str | None = "0007_public_access_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("credential_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=80), nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False),
        sa.Column("public_token_id", sa.String(length=120), nullable=False),
        sa.Column("token_secret_hash", sa.String(length=255), nullable=False),
        sa.Column("token_hash_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("policy_profile", sa.String(length=80), nullable=False),
        sa.Column("origin_id", sa.String(length=36), nullable=True),
        sa.Column("canonical_origin_hash", sa.String(length=128), nullable=True),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("anonymous_user_id", sa.String(length=120), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_sessions.id"]),
        sa.ForeignKeyConstraint(["credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["origin_id"], ["credential_allowed_origins.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.CheckConstraint("status in ('active', 'completed', 'expired', 'revoked', 'blocked')", name="ck_public_sessions_status"),
        sa.CheckConstraint("message_count >= 0", name="ck_public_sessions_message_count_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token_id", name="uq_public_sessions_public_token_id"),
    )
    op.create_index("ix_public_sessions_organisation_id", "public_sessions", ["organisation_id"])
    op.create_index("ix_public_sessions_workspace_id", "public_sessions", ["workspace_id"])
    op.create_index("ix_public_sessions_credential_id", "public_sessions", ["credential_id"])
    op.create_index("ix_public_sessions_tenant_workspace", "public_sessions", ["organisation_id", "workspace_id"])
    op.create_index("ix_public_sessions_tenant_credential", "public_sessions", ["organisation_id", "workspace_id", "credential_id"])
    op.create_index("ix_public_sessions_credential_status", "public_sessions", ["credential_id", "status"])
    op.create_index("ix_public_sessions_status_expires_at", "public_sessions", ["status", "expires_at"])
    op.create_index("ix_public_sessions_last_activity_at", "public_sessions", ["last_activity_at"])
    op.create_index("ix_public_sessions_conversation_id", "public_sessions", ["conversation_id"])
    op.create_index("ix_public_sessions_deleted_at", "public_sessions", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_public_sessions_deleted_at", table_name="public_sessions")
    op.drop_index("ix_public_sessions_conversation_id", table_name="public_sessions")
    op.drop_index("ix_public_sessions_last_activity_at", table_name="public_sessions")
    op.drop_index("ix_public_sessions_status_expires_at", table_name="public_sessions")
    op.drop_index("ix_public_sessions_credential_status", table_name="public_sessions")
    op.drop_index("ix_public_sessions_tenant_credential", table_name="public_sessions")
    op.drop_index("ix_public_sessions_tenant_workspace", table_name="public_sessions")
    op.drop_index("ix_public_sessions_credential_id", table_name="public_sessions")
    op.drop_index("ix_public_sessions_workspace_id", table_name="public_sessions")
    op.drop_index("ix_public_sessions_organisation_id", table_name="public_sessions")
    op.drop_table("public_sessions")

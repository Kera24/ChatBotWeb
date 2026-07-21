"""create public credentials and widget configuration

Revision ID: 0007_public_access_config
Revises: 0006_review_annotations
Create Date: 2026-07-14
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_public_access_config"
down_revision: str | None = "0006_review_annotations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("credential_type", sa.String(length=60), nullable=False),
        sa.Column("public_identifier", sa.String(length=255), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False),
        sa.Column("policy_profile", sa.String(length=80), nullable=False),
        sa.Column("capabilities_json", sa.JSON(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("rotation_group_id", sa.String(length=36), nullable=True),
        sa.Column("parent_credential_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["parent_credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_identifier", name="uq_public_credentials_public_identifier"),
    )
    op.create_index("ix_public_credentials_organisation_id", "public_credentials", ["organisation_id"])
    op.create_index("ix_public_credentials_workspace_id", "public_credentials", ["workspace_id"])
    op.create_index("ix_public_credentials_created_by_user_id", "public_credentials", ["created_by_user_id"])
    op.create_index("ix_public_credentials_tenant_workspace", "public_credentials", ["organisation_id", "workspace_id"])
    op.create_index("ix_public_credentials_workspace_type_environment", "public_credentials", ["workspace_id", "credential_type", "environment"])
    op.create_index("ix_public_credentials_status", "public_credentials", ["status"])
    op.create_index("ix_public_credentials_type_environment_status", "public_credentials", ["credential_type", "environment", "status"])
    op.create_index("ix_public_credentials_expires_at", "public_credentials", ["expires_at"])
    op.create_index("ix_public_credentials_deleted_at", "public_credentials", ["deleted_at"])
    op.create_index("ix_public_credentials_rotation_group", "public_credentials", ["rotation_group_id"])
    op.create_index("ix_public_credentials_parent", "public_credentials", ["parent_credential_id"])

    op.create_table(
        "credential_allowed_origins",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("credential_id", sa.String(length=36), nullable=False),
        sa.Column("scheme", sa.String(length=12), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("wildcard_subdomains", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("environment", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id", "scheme", "hostname", "port", "wildcard_subdomains", "environment", name="uq_credential_allowed_origins_normalised"),
    )
    op.create_index("ix_credential_allowed_origins_organisation_id", "credential_allowed_origins", ["organisation_id"])
    op.create_index("ix_credential_allowed_origins_workspace_id", "credential_allowed_origins", ["workspace_id"])
    op.create_index("ix_credential_allowed_origins_credential_id", "credential_allowed_origins", ["credential_id"])
    op.create_index("ix_credential_allowed_origins_tenant_workspace", "credential_allowed_origins", ["organisation_id", "workspace_id"])
    op.create_index("ix_credential_allowed_origins_credential_active", "credential_allowed_origins", ["credential_id", "active"])

    op.create_table(
        "widget_configurations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("credential_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
        sa.Column("bot_name", sa.String(length=120), nullable=False),
        sa.Column("welcome_message", sa.Text(), nullable=False),
        sa.Column("launcher_label", sa.String(length=80), nullable=False),
        sa.Column("primary_colour", sa.String(length=16), nullable=False),
        sa.Column("secondary_colour", sa.String(length=16), nullable=True),
        sa.Column("logo_path", sa.String(length=512), nullable=True),
        sa.Column("avatar_path", sa.String(length=512), nullable=True),
        sa.Column("position", sa.String(length=40), nullable=False),
        sa.Column("theme_mode", sa.String(length=40), nullable=False),
        sa.Column("suggested_questions_json", sa.JSON(), nullable=True),
        sa.Column("fallback_contact_text", sa.String(length=500), nullable=True),
        sa.Column("privacy_notice_text", sa.String(length=1000), nullable=True),
        sa.Column("privacy_notice_url", sa.String(length=512), nullable=True),
        sa.Column("terms_url", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("show_citations", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("allow_conversation_history", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("max_initial_suggestions", sa.Integer(), server_default="3", nullable=False),
        sa.Column("configuration_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id", name="uq_widget_configurations_credential"),
    )
    op.create_index("ix_widget_configurations_organisation_id", "widget_configurations", ["organisation_id"])
    op.create_index("ix_widget_configurations_workspace_id", "widget_configurations", ["workspace_id"])
    op.create_index("ix_widget_configurations_credential_id", "widget_configurations", ["credential_id"])
    op.create_index("ix_widget_configurations_tenant_workspace", "widget_configurations", ["organisation_id", "workspace_id"])
    op.create_index("ix_widget_configurations_credential_status", "widget_configurations", ["credential_id", "status"])
    op.create_index("ix_widget_configurations_workspace_status", "widget_configurations", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_widget_configurations_workspace_status", table_name="widget_configurations")
    op.drop_index("ix_widget_configurations_credential_status", table_name="widget_configurations")
    op.drop_index("ix_widget_configurations_tenant_workspace", table_name="widget_configurations")
    op.drop_index("ix_widget_configurations_credential_id", table_name="widget_configurations")
    op.drop_index("ix_widget_configurations_workspace_id", table_name="widget_configurations")
    op.drop_index("ix_widget_configurations_organisation_id", table_name="widget_configurations")
    op.drop_table("widget_configurations")

    op.drop_index("ix_credential_allowed_origins_credential_active", table_name="credential_allowed_origins")
    op.drop_index("ix_credential_allowed_origins_tenant_workspace", table_name="credential_allowed_origins")
    op.drop_index("ix_credential_allowed_origins_credential_id", table_name="credential_allowed_origins")
    op.drop_index("ix_credential_allowed_origins_workspace_id", table_name="credential_allowed_origins")
    op.drop_index("ix_credential_allowed_origins_organisation_id", table_name="credential_allowed_origins")
    op.drop_table("credential_allowed_origins")

    op.drop_index("ix_public_credentials_parent", table_name="public_credentials")
    op.drop_index("ix_public_credentials_rotation_group", table_name="public_credentials")
    op.drop_index("ix_public_credentials_deleted_at", table_name="public_credentials")
    op.drop_index("ix_public_credentials_expires_at", table_name="public_credentials")
    op.drop_index("ix_public_credentials_type_environment_status", table_name="public_credentials")
    op.drop_index("ix_public_credentials_status", table_name="public_credentials")
    op.drop_index("ix_public_credentials_workspace_type_environment", table_name="public_credentials")
    op.drop_index("ix_public_credentials_tenant_workspace", table_name="public_credentials")
    op.drop_index("ix_public_credentials_created_by_user_id", table_name="public_credentials")
    op.drop_index("ix_public_credentials_workspace_id", table_name="public_credentials")
    op.drop_index("ix_public_credentials_organisation_id", table_name="public_credentials")
    op.drop_table("public_credentials")



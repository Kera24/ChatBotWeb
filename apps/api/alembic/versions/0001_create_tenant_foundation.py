"""create tenant foundation

Revision ID: 0001_create_tenant_foundation
Revises: 
Create Date: 2026-07-07
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_create_tenant_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("plan_key", sa.String(length=80), server_default="mvp", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_organisations_slug", "organisations", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column("auth_provider", sa.String(length=80), nullable=True),
        sa.Column("external_auth_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auth_provider", "external_auth_id", name="uq_users_auth_identity"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("default_language", sa.String(length=16), server_default="en", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "slug", name="uq_workspaces_organisation_slug"),
    )
    op.create_index("ix_workspaces_organisation_id", "workspaces", ["organisation_id"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "user_id", name="uq_memberships_organisation_user"),
    )
    op.create_index("ix_memberships_organisation_id", "memberships", ["organisation_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_organisation_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_index("ix_workspaces_organisation_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_organisations_slug", table_name="organisations")
    op.drop_table("organisations")

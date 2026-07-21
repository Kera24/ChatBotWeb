"""add widget knowledge scope and installation observations

Revision ID: 0012_widget_knowledge_preview_installation
Revises: 0011_widget_embed_preferences
Create Date: 2026-07-21
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_widget_knowledge_preview_installation"
down_revision: str | None = "0011_widget_embed_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widget_configuration_revisions", sa.Column("knowledge_scope_json", sa.JSON(), nullable=True))
    op.create_table(
        "widget_installation_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("public_credential_id", sa.String(length=36), nullable=False),
        sa.Column("origin", sa.String(length=512), nullable=False),
        sa.Column("sdk_version", sa.String(length=80), nullable=True),
        sa.Column("protocol_major", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"]),
        sa.ForeignKeyConstraint(["public_credential_id"], ["public_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("widget_id", "public_credential_id", "origin", name="uq_widget_installation_observation_origin"),
    )
    op.create_index("ix_widget_installation_observations_widget", "widget_installation_observations", ["widget_id"])
    op.create_index("ix_widget_installation_observations_tenant_workspace", "widget_installation_observations", ["organisation_id", "workspace_id"])
    op.create_index("ix_widget_installation_observations_last_seen", "widget_installation_observations", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_widget_installation_observations_last_seen", table_name="widget_installation_observations")
    op.drop_index("ix_widget_installation_observations_tenant_workspace", table_name="widget_installation_observations")
    op.drop_index("ix_widget_installation_observations_widget", table_name="widget_installation_observations")
    op.drop_table("widget_installation_observations")
    op.drop_column("widget_configuration_revisions", "knowledge_scope_json")
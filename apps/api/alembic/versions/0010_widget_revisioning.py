"""add widget revisioning

Revision ID: 0010_widget_revisioning
Revises: 0009_public_messages
Create Date: 2026-07-20
"""
from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0010_widget_revisioning"
down_revision: str | None = "0009_public_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONFIG_COLUMNS = [
    "bot_name",
    "welcome_message",
    "launcher_label",
    "primary_colour",
    "secondary_colour",
    "logo_path",
    "avatar_path",
    "position",
    "theme_mode",
    "suggested_questions_json",
    "fallback_contact_text",
    "privacy_notice_text",
    "privacy_notice_url",
    "terms_url",
    "language",
    "show_citations",
    "allow_conversation_history",
    "max_initial_suggestions",
]


def upgrade() -> None:
    op.create_table(
        "widgets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("public_credential_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("operational_status", sa.String(length=40), server_default="enabled", nullable=False),
        sa.Column("pilot_status", sa.String(length=40), server_default="not_approved", nullable=False),
        sa.Column("release_channel", sa.String(length=40), server_default="pilot", nullable=False),
        sa.Column("active_published_revision_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["public_credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_credential_id", name="uq_widgets_public_credential"),
    )
    op.create_index("ix_widgets_active_revision", "widgets", ["active_published_revision_id"])
    op.create_index("ix_widgets_public_credential_id", "widgets", ["public_credential_id"])
    op.create_index("ix_widgets_tenant_workspace", "widgets", ["organisation_id", "workspace_id"])
    op.create_index("ix_widgets_workspace_id", "widgets", ["workspace_id"])
    op.create_index("ix_widgets_workspace_status", "widgets", ["workspace_id", "operational_status"])

    op.create_table(
        "widget_configuration_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("widget_id", sa.String(length=36), nullable=False),
        sa.Column("public_credential_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="draft", nullable=False),
        sa.Column("concurrency_version", sa.Integer(), server_default="1", nullable=False),
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
        sa.Column("show_citations", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("allow_conversation_history", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("max_initial_suggestions", sa.Integer(), server_default="3", nullable=False),
        sa.Column("configuration_hash", sa.String(length=128), nullable=True),
        sa.Column("source_revision_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("published_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["public_credential_id"], ["public_credentials.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_revision_id"], ["widget_configuration_revisions.id"]),
        sa.ForeignKeyConstraint(["widget_id"], ["widgets.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("widget_id", "revision_number", name="uq_widget_configuration_revisions_widget_number"),
    )
    op.create_index("ix_widget_configuration_revisions_credential_status", "widget_configuration_revisions", ["public_credential_id", "status"])
    op.create_index("ix_widget_configuration_revisions_created_by_user_id", "widget_configuration_revisions", ["created_by_user_id"])
    op.create_index("ix_widget_configuration_revisions_published_at", "widget_configuration_revisions", ["published_at"])
    op.create_index("ix_widget_configuration_revisions_published_by_user_id", "widget_configuration_revisions", ["published_by_user_id"])
    op.create_index("ix_widget_configuration_revisions_public_credential_id", "widget_configuration_revisions", ["public_credential_id"])
    op.create_index("ix_widget_configuration_revisions_tenant_workspace", "widget_configuration_revisions", ["organisation_id", "workspace_id"])
    op.create_index("ix_widget_configuration_revisions_widget_id", "widget_configuration_revisions", ["widget_id"])
    op.create_index("ix_widget_configuration_revisions_widget_number", "widget_configuration_revisions", ["widget_id", "revision_number"])
    op.create_index("ix_widget_configuration_revisions_widget_status", "widget_configuration_revisions", ["widget_id", "status"])
    op.create_index("ix_widget_configuration_revisions_workspace_id", "widget_configuration_revisions", ["workspace_id"])

    _backfill_existing_widget_configurations()


def downgrade() -> None:
    op.drop_index("ix_widget_configuration_revisions_workspace_id", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_widget_status", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_widget_number", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_widget_id", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_tenant_workspace", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_public_credential_id", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_published_by_user_id", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_published_at", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_created_by_user_id", table_name="widget_configuration_revisions")
    op.drop_index("ix_widget_configuration_revisions_credential_status", table_name="widget_configuration_revisions")
    op.drop_table("widget_configuration_revisions")
    op.drop_index("ix_widgets_workspace_status", table_name="widgets")
    op.drop_index("ix_widgets_workspace_id", table_name="widgets")
    op.drop_index("ix_widgets_tenant_workspace", table_name="widgets")
    op.drop_index("ix_widgets_public_credential_id", table_name="widgets")
    op.drop_index("ix_widgets_active_revision", table_name="widgets")
    op.drop_table("widgets")


def _backfill_existing_widget_configurations() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT * FROM widget_configurations")).mappings().all()
    for row in rows:
        widget_id = str(uuid4())
        revision_id = str(uuid4())
        revision_number = max(int(row.get("configuration_version") or 0), 1)
        active_revision_id = revision_id if row.get("status") == "published" else None
        connection.execute(
            sa.text(
                """
                INSERT INTO widgets (
                    id, organisation_id, workspace_id, public_credential_id, display_name,
                    operational_status, pilot_status, release_channel, active_published_revision_id,
                    created_at, updated_at
                ) VALUES (
                    :id, :organisation_id, :workspace_id, :public_credential_id, :display_name,
                    'enabled', 'not_approved', 'pilot', :active_published_revision_id,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "id": widget_id,
                "organisation_id": row["organisation_id"],
                "workspace_id": row["workspace_id"],
                "public_credential_id": row["credential_id"],
                "display_name": row["bot_name"],
                "active_published_revision_id": active_revision_id,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
        values = {
            "id": revision_id,
            "organisation_id": row["organisation_id"],
            "workspace_id": row["workspace_id"],
            "widget_id": widget_id,
            "public_credential_id": row["credential_id"],
            "revision_number": revision_number,
            "status": "published" if row.get("status") == "published" else "draft",
            "concurrency_version": 1,
            "source_revision_id": None,
            "created_by_user_id": None,
            "published_by_user_id": None,
            "published_at": row["published_at"] if row.get("status") == "published" else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "configuration_hash": None,
        }
        values.update({column: row[column] for column in CONFIG_COLUMNS})
        connection.execute(
            sa.text(
                """
                INSERT INTO widget_configuration_revisions (
                    id, organisation_id, workspace_id, widget_id, public_credential_id,
                    revision_number, status, concurrency_version, bot_name, welcome_message,
                    launcher_label, primary_colour, secondary_colour, logo_path, avatar_path,
                    position, theme_mode, suggested_questions_json, fallback_contact_text,
                    privacy_notice_text, privacy_notice_url, terms_url, language, show_citations,
                    allow_conversation_history, max_initial_suggestions, configuration_hash,
                    source_revision_id, created_by_user_id, published_by_user_id, published_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :organisation_id, :workspace_id, :widget_id, :public_credential_id,
                    :revision_number, :status, :concurrency_version, :bot_name, :welcome_message,
                    :launcher_label, :primary_colour, :secondary_colour, :logo_path, :avatar_path,
                    :position, :theme_mode, :suggested_questions_json, :fallback_contact_text,
                    :privacy_notice_text, :privacy_notice_url, :terms_url, :language, :show_citations,
                    :allow_conversation_history, :max_initial_suggestions, :configuration_hash,
                    :source_revision_id, :created_by_user_id, :published_by_user_id, :published_at,
                    :created_at, :updated_at
                )
                """
            ),
            values,
        )
"""create review annotations

Revision ID: 0006_review_annotations
Revises: 0005_conversation_schema
Create Date: 2026-07-13
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_review_annotations"
down_revision: str | None = "0005_conversation_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_annotations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_message_id", sa.String(length=36), nullable=False),
        sa.Column("review_status", sa.String(length=40), server_default="open", nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["chat_messages.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_sessions.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_message_id", name="uq_review_annotations_assistant_message"),
    )
    op.create_index("ix_review_annotations_organisation_id", "review_annotations", ["organisation_id"])
    op.create_index("ix_review_annotations_workspace_id", "review_annotations", ["workspace_id"])
    op.create_index("ix_review_annotations_conversation_id", "review_annotations", ["conversation_id"])
    op.create_index("ix_review_annotations_assistant_message_id", "review_annotations", ["assistant_message_id"])
    op.create_index("ix_review_annotations_reviewed_by", "review_annotations", ["reviewed_by"])
    op.create_index("ix_review_annotations_tenant_workspace", "review_annotations", ["organisation_id", "workspace_id"])
    op.create_index("ix_review_annotations_status", "review_annotations", ["organisation_id", "workspace_id", "review_status"])
    op.create_index("ix_review_annotations_message", "review_annotations", ["assistant_message_id"])


def downgrade() -> None:
    op.drop_index("ix_review_annotations_message", table_name="review_annotations")
    op.drop_index("ix_review_annotations_status", table_name="review_annotations")
    op.drop_index("ix_review_annotations_tenant_workspace", table_name="review_annotations")
    op.drop_index("ix_review_annotations_reviewed_by", table_name="review_annotations")
    op.drop_index("ix_review_annotations_assistant_message_id", table_name="review_annotations")
    op.drop_index("ix_review_annotations_conversation_id", table_name="review_annotations")
    op.drop_index("ix_review_annotations_workspace_id", table_name="review_annotations")
    op.drop_index("ix_review_annotations_organisation_id", table_name="review_annotations")
    op.drop_table("review_annotations")

"""add widget embed preferences

Revision ID: 0011_widget_embed_preferences
Revises: 0010_widget_revisioning
Create Date: 2026-07-20
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_widget_embed_preferences"
down_revision: str | None = "0010_widget_revisioning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("widgets", sa.Column("embed_version_mode", sa.String(length=40), server_default="managed_major", nullable=False))
    op.add_column("widgets", sa.Column("pinned_sdk_version", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("widgets", "pinned_sdk_version")
    op.drop_column("widgets", "embed_version_mode")
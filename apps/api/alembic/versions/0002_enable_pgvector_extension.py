"""enable pgvector extension

Revision ID: 0002_enable_pgvector_extension
Revises: 0001_create_tenant_foundation
Create Date: 2026-07-08
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002_enable_pgvector_extension"
down_revision: str | None = "0001_create_tenant_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector")

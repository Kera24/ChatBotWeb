"""lexical search full-text index

Revision ID: 0021_lexical_search_index
Revises: 0020_email_verification
Create Date: 2026-08-10
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0021_lexical_search_index"
down_revision: str | None = "0020_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Retrieval V2 Phase 1 - Hybrid Retrieval (docs/future/HybridRetrieval.md,
# docs/sops/adding-hybrid-retrieval.md). Postgres-only functional GIN index
# backing app.services.lexical_search's websearch_to_tsquery/ts_rank_cd
# queries. No column changes - purely additive and fully reversible (drop
# index); SQLite has no equivalent (app.services.lexical_search falls back to
# a Python term-overlap scorer there instead), so this migration is a no-op
# on that dialect, matching the existing pgvector-extension migration's
# dialect-guard pattern (0002_enable_pgvector_extension.py).
def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_content_fts "
            "ON chunks USING GIN (to_tsvector('english', content))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chunks_content_fts")

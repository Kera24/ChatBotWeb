"""pgvector HNSW approximate-nearest-neighbour index (Retrieval & Answer
Pipeline V3 experiment, docs/future/RetrievalOptimisation.md)

Revision ID: 0022_pgvector_hnsw_index
Revises: 0021_lexical_search_index
Create Date: 2026-08-14
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0022_pgvector_hnsw_index"
down_revision: str | None = "0021_lexical_search_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# pgvector's own library defaults (m=16, ef_construction=64) - deliberately
# NOT tuned against this project's tiny synthetic evaluation corpus (Part 6's
# explicit "do not over-tune on the small synthetic corpus" instruction).
# Mirrored in app.core.config.settings.PGVECTOR_HNSW_M/PGVECTOR_HNSW_EF_CONSTRUCTION
# purely as documentation/inspection constants - this migration does not read
# app settings (migrations must be reproducible independent of whatever
# environment variables happen to be set when they run), so the literal
# values are duplicated here deliberately; keep both in sync if ever revisited.
_HNSW_M = 16
_HNSW_EF_CONSTRUCTION = 64


# Postgres-only functional index accelerating app.services.vector_search's
# `ORDER BY embedding_vector <=> ... LIMIT` queries via approximate nearest-
# neighbour search - purely additive (no column change) and fully reversible
# (drop index), matching 0021_lexical_search_index's dialect-guard pattern.
#
# Deliberately NOT wired into any application code path (vector_search.py is
# completely unmodified by this migration) - creating the index makes it
# AVAILABLE to Postgres's query planner, but the existing exact `<=>` query
# is unchanged, and on the modest table sizes this project's evaluation
# corpora and current production scale produce, the planner overwhelmingly
# still prefers a sequential scan (see the V3 evaluation report's HNSW
# section for the measured evidence). This keeps `dense_only`'s exact-search
# baseline behaviour unmutated by this migration alone, per the V3 task's
# "preserve production baseline" requirement - HNSW is evaluated as a
# measured, opt-in candidate (app.operations.eval_hnsw_benchmark), not
# silently promoted by index existence.
def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_chunks_embedding_vector_hnsw "
            f"ON chunks USING hnsw (embedding_vector vector_cosine_ops) "
            f"WITH (m = {_HNSW_M}, ef_construction = {_HNSW_EF_CONSTRUCTION})"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_vector_hnsw")

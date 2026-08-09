"""Production-path integration tests for app.services.vector_search's real
PostgreSQL/pgvector branch (`_search_postgresql`) - the branch
`db.bind.dialect.name == "postgresql"` selects in `search_embedded_chunks`,
which every other test in this suite (SQLite, in-memory) never exercises.

Requires a reachable Postgres server with the `vector` extension installable
(see docker-compose.yml's `postgres` service, image `pgvector/pgvector:pg16`
- the same image/service used for local dev). The whole module is skipped,
not failed, when no Postgres is reachable, so `npm run api:test` stays fully
runnable without Docker. Run this tier explicitly via
`npm run api:test:postgres` (brings the `postgres` service up first).

Schema setup uses `Base.metadata.create_all()` against a dedicated
`chatbotweb_test` database - the exact same approach every SQLite test in
this suite already uses, just pointed at Postgres instead of `:memory:` -
not Alembic migrations. This validates the ORM-defined schema (including
`app.db.types.PgVector`, which compiles to a real `vector(n)` column on
Postgres) directly, independent of migration history/state. `PgVector`'s
default/production dimension is 1536 (see `apps/api/alembic/versions/
0003_create_document_chunk_schema.py`'s `PgVector(1536)` column and
`settings.EMBEDDING_DIMENSION`'s default) - unlike SQLite, where PgVector
compiles to `TEXT` and any vector length is silently accepted, Postgres
enforces this dimension on INSERT, so every vector in this file is padded to
exactly that width (see `ControlledEmbeddingProvider` below).

Since a fresh database-per-test would make this tier too slow to be useful
day-to-day, all tests in this module share one long-lived schema (module
-scoped engine) and rely on distinct `suffix` values per test (via
`_seed_tenant`'s `suffix` argument, which only needs to be unique *within
this file* - `Organisation.slug` has a real unique constraint) for isolation
*within* one run - incidentally a more production-realistic setup than a
wiped database, since it proves tenant-scoping still holds with OTHER
tenants' rows already present in the same tables, the way a real
multi-tenant Postgres database always looks.

Isolation *across* separate runs (this file executed twice back to back, or
after a previous run crashed mid-test) is a different problem: `suffix`
values are fixed strings, not randomly generated per run, so without a
reset, a second run's `INSERT`s collide with the first run's leftover rows
on `Organisation.slug`'s unique constraint. `pg_engine` below resets the
schema (`Base.metadata.drop_all` then `create_all`) both before the module's
tests run and after, so every run starts from a byte-identical empty slate
regardless of how the previous run ended - this is the "deterministic
truncate/reset with safe teardown" isolation strategy, scoped to the
dedicated `chatbotweb_test` database only (see `POSTGRES_TEST_DATABASE_URL`
above), never the dev/prod database at `DATABASE_URL`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.vector_search import search_embedded_chunks

POSTGRES_TEST_DATABASE_URL = os.environ.get(
    "POSTGRES_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb_test",
)

# The canonical production embedding dimension (item 7 of this task) - see
# this module's docstring for where it comes from.
PRODUCTION_EMBEDDING_DIMENSION = 1536


def _postgres_reachable() -> bool:
    try:
        admin_url = make_url(POSTGRES_TEST_DATABASE_URL).set(database="postgres")
        engine = create_engine(admin_url, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=(
        "Postgres/pgvector integration tier requires a reachable server - run "
        "`docker compose up -d postgres` and `npm run api:test:postgres` "
        "(or set POSTGRES_TEST_DATABASE_URL). Skipped, not failed, so "
        "`npm run api:test` stays runnable without Docker."
    ),
)


def _ensure_test_database_exists() -> None:
    url = make_url(POSTGRES_TEST_DATABASE_URL)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="module")
def pg_engine():
    _ensure_test_database_exists()
    engine = create_engine(POSTGRES_TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    # Reset BEFORE running: makes this run self-healing regardless of
    # whether the previous run's own teardown got a chance to execute (a
    # killed process, a Ctrl+C, a Docker restart mid-run all skip Python
    # teardown code entirely) - the fixed `suffix` values in this file's
    # `_seed_tenant` calls are only unique within a single run, so starting
    # from a genuinely empty schema is what actually fixes the duplicate-key
    # failures on a second/stale run, not just a best-effort cleanup after.
    # drop_all's default checkfirst=True makes this safe to run against an
    # already-empty (or brand new) database too.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    # Reset AFTER too, so a normal (non-crashed) run leaves nothing behind
    # either - belt-and-suspenders with the pre-run reset above. Runs even
    # if a test inside this module raised, since pytest always resumes a
    # yield-fixture's teardown code on the way out of the module's tests.
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    yield session
    session.close()


@dataclass(frozen=True)
class ControlledEmbeddingProvider:
    """Same rationale as tests/test_vector_search_similarity_threshold.py's
    provider of the same name: fixed, hand-picked vectors per exact input
    text, so a test can force an exact known cosine-similarity score,
    independent of any real embedding model's semantic quality. Signatures
    are zero-padded up to PRODUCTION_EMBEDDING_DIMENSION - a shared all-zero
    suffix on both operands contributes 0 to the dot product and does not
    change either vector's direction, so padding never distorts the
    intended similarity score."""

    vectors: dict[str, list[float]] = field(default_factory=dict)
    provider_name: str = "controlled-postgres-test"
    model_name: str = "controlled-postgres-test-v1"
    dimension: int = PRODUCTION_EMBEDDING_DIMENSION

    def embed(self, text_value: str) -> list[float]:
        signature = self.vectors[text_value]
        return list(signature) + [0.0] * (self.dimension - len(signature))


def _seed_tenant(db: Session, *, suffix: str) -> tuple[str, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"pg-org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"pg-workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"pg-owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation.id, workspace.id


def _seed_chunk(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    key: str,
    content: str,
    provider: ControlledEmbeddingProvider,
    document_status: str = "ready",
    chunk_status: str = "ready",
    version_status: str = "ready",
) -> tuple[str, str]:
    """Returns (document_id, chunk_id)."""
    document = Document(
        organisation_id=organisation_id, workspace_id=workspace_id, title=key, source_type="txt",
        source_key=f"{key}.txt", status=document_status,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id,
        version_number=1, checksum=f"checksum-{key}", processing_status=version_status,
    )
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=key, status=chunk_status,
        embedding_provider=provider.provider_name, embedding_model=provider.model_name, embedding_dimension=provider.dimension,
        embedding_created_at=datetime.now(timezone.utc), embedding_vector=provider.embed(content),
    )
    db.add(chunk)
    db.commit()
    return document.id, chunk.id


# --- vector insert/read ------------------------------------------------------


def test_vector_insert_and_read_round_trips_at_production_dimension(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="insert-read")
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0, 0.0], "matching content": [1.0, 0.0, 0.0]})
    document_id, chunk_id = _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="matching content", provider=provider)

    stored_raw = db.execute(text("SELECT embedding_vector FROM chunks WHERE id = :id"), {"id": chunk_id}).scalar()
    assert stored_raw is not None
    assert stored_raw.count(",") == PRODUCTION_EMBEDDING_DIMENSION - 1  # 1536 components -> 1535 separators

    matches = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)
    assert len(matches) == 1
    assert matches[0].chunk_id == chunk_id
    assert matches[0].document_id == document_id
    assert matches[0].score == pytest.approx(1.0)


# --- similarity ordering ------------------------------------------------------


def test_similarity_ordering_is_correct(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="ordering")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0],
        "best match": [1.0, 0.0],        # cosine similarity = 1.0
        "medium match": [0.7, 0.7],       # cosine similarity ~ 0.707
        "worst match": [0.0, 1.0],        # cosine similarity = 0.0
    })
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="worst", content="worst match", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="best", content="best match", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="medium", content="medium match", provider=provider)

    matches = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)

    assert [match.source_title for match in matches] == ["best", "medium", "worst"]
    assert matches[0].score > matches[1].score > matches[2].score


# --- minimum similarity threshold --------------------------------------------


def test_minimum_similarity_threshold_excludes_low_scoring_matches(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="threshold")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0, 0.0],
        "relevant content": [1.0, 0.0, 0.0],
        "irrelevant content": [-1.0, 0.0, 0.0],
    })
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="relevant", content="relevant content", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="irrelevant", content="irrelevant content", provider=provider)

    unfiltered = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)
    assert {m.source_title for m in unfiltered} == {"relevant", "irrelevant"}

    filtered = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, min_similarity_score=0.5,
    )
    assert [m.source_title for m in filtered] == ["relevant"]


def test_minimum_similarity_threshold_boundary_is_inclusive(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="threshold-boundary")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0],
        "exact match content": [0.6, 0.8],  # cosine similarity to [1, 0] is exactly 0.6
    })
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="exact", content="exact match content", provider=provider)

    at_threshold = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, min_similarity_score=0.6,
    )
    assert len(at_threshold) == 1

    just_above = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, min_similarity_score=0.6000001,
    )
    assert just_above == []


# --- organisation isolation ---------------------------------------------------


def test_organisation_isolation_excludes_other_organisations_chunks(db: Session) -> None:
    org_a_id, ws_a_id = _seed_tenant(db, suffix="org-isolation-a")
    org_b_id, ws_b_id = _seed_tenant(db, suffix="org-isolation-b")
    # Identical query vector AND identical content in both organisations -
    # if isolation were broken, org A's query would also return org B's chunk.
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "shared content": [1.0, 0.0]})
    doc_a_id, _ = _seed_chunk(db, organisation_id=org_a_id, workspace_id=ws_a_id, key="doc-a", content="shared content", provider=provider)
    _seed_chunk(db, organisation_id=org_b_id, workspace_id=ws_b_id, key="doc-b", content="shared content", provider=provider)

    matches = search_embedded_chunks(db, organisation_id=org_a_id, workspace_id=ws_a_id, query="the query", limit=10, provider=provider)

    assert len(matches) == 1
    assert matches[0].document_id == doc_a_id


# --- workspace isolation -------------------------------------------------------


def test_workspace_isolation_excludes_other_workspaces_chunks_in_same_organisation(db: Session) -> None:
    organisation_id, ws_1_id = _seed_tenant(db, suffix="ws-isolation")
    # A second workspace under the SAME organisation - proves the isolation
    # boundary is workspace_id, not just organisation_id.
    workspace_2 = Workspace(organisation_id=organisation_id, name="Second Workspace", slug="pg-workspace-ws-isolation-2", status="active", default_language="en")
    db.add(workspace_2)
    db.commit()
    ws_2_id = workspace_2.id

    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "shared content": [1.0, 0.0]})
    doc_1_id, _ = _seed_chunk(db, organisation_id=organisation_id, workspace_id=ws_1_id, key="doc-ws1", content="shared content", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=ws_2_id, key="doc-ws2", content="shared content", provider=provider)

    matches = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=ws_1_id, query="the query", limit=10, provider=provider)

    assert len(matches) == 1
    assert matches[0].document_id == doc_1_id


# --- assistant/document scope isolation ---------------------------------------


def test_document_scope_isolation_restricts_to_specified_document_ids(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="doc-scope")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0], "in scope content": [1.0, 0.0], "out of scope content": [1.0, 0.0],
    })
    in_scope_doc_id, _ = _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="in-scope", content="in scope content", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="out-of-scope", content="out of scope content", provider=provider)

    matches = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, document_ids=[in_scope_doc_id],
    )

    assert len(matches) == 1
    assert matches[0].document_id == in_scope_doc_id


# --- document_ids=None behavior ------------------------------------------------


def test_document_ids_none_returns_unrestricted_workspace_results(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="doc-ids-none")
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "doc one": [1.0, 0.0], "doc two": [1.0, 0.0]})
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="one", content="doc one", provider=provider)
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="two", content="doc two", provider=provider)

    matches = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, document_ids=None,
    )

    assert {m.source_title for m in matches} == {"one", "two"}


# --- document_ids=[] behavior ---------------------------------------------------


def test_document_ids_empty_list_returns_no_results(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="doc-ids-empty")
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "some content": [1.0, 0.0]})
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="only-doc", content="some content", provider=provider)

    matches = search_embedded_chunks(
        db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider, document_ids=[],
    )

    assert matches == []


# --- archived/unavailable document exclusion (regression test) ---------------


def test_archived_document_is_excluded_from_retrieval(db: Session) -> None:
    """Regression test for a real defect found while building this tier:
    app.services.document_lifecycle.transition_document_status's "archived"
    transition only sets Document.status/archived_at - it never touches
    active_document_version_id or chunk status - so _search_postgresql (and
    _search_sqlite) previously kept matching an archived document's chunks
    forever. Fixed by adding a `Document.status == "ready"` condition to
    both backends (app.services.vector_search)."""
    organisation_id, workspace_id = _seed_tenant(db, suffix="archived-exclusion")
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "archived content": [1.0, 0.0], "active content": [1.0, 0.0]})
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="archived", content="archived content", provider=provider, document_status="archived")
    active_doc_id, _ = _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="active", content="active content", provider=provider, document_status="ready")

    matches = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=10, provider=provider)

    assert len(matches) == 1
    assert matches[0].document_id == active_doc_id


# --- correct top-k behavior -----------------------------------------------------


def test_top_k_limit_returns_only_the_best_k_matches_in_order(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="top-k")
    provider = ControlledEmbeddingProvider(vectors={
        "the query": [1.0, 0.0, 0.0, 0.0],
        "rank 1": [1.0, 0.0, 0.0, 0.0],     # score 1.0
        "rank 2": [0.9, 0.1, 0.0, 0.0],
        "rank 3": [0.8, 0.2, 0.0, 0.0],
        "rank 4": [0.7, 0.3, 0.0, 0.0],
        "rank 5": [0.6, 0.4, 0.0, 0.0],
    })
    for key, content in [("r1", "rank 1"), ("r2", "rank 2"), ("r3", "rank 3"), ("r4", "rank 4"), ("r5", "rank 5")]:
        _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key=key, content=content, provider=provider)

    matches = search_embedded_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="the query", limit=3, provider=provider)

    assert len(matches) == 3
    assert [m.source_title for m in matches] == ["r1", "r2", "r3"]


# --- no cross-tenant retrieval ---------------------------------------------------


def test_no_cross_tenant_retrieval_even_when_document_id_belongs_to_another_organisation(db: Session) -> None:
    """A document_ids scope naming another tenant's document must never leak
    that tenant's content - the WHERE clause filters by organisation_id/
    workspace_id first, so an out-of-tenant id in the IN-list simply matches
    nothing, rather than being trusted as an authorization boundary on its
    own (defense in depth: callers are also expected to only ever resolve
    document_ids from the caller's own tenant, but this proves the query
    itself does not silently trust an attacker-supplied id)."""
    org_a_id, ws_a_id = _seed_tenant(db, suffix="cross-tenant-a")
    org_b_id, ws_b_id = _seed_tenant(db, suffix="cross-tenant-b")
    provider = ControlledEmbeddingProvider(vectors={"the query": [1.0, 0.0], "org b secret content": [1.0, 0.0]})
    org_b_doc_id, _ = _seed_chunk(db, organisation_id=org_b_id, workspace_id=ws_b_id, key="org-b-doc", content="org b secret content", provider=provider)

    matches = search_embedded_chunks(
        db, organisation_id=org_a_id, workspace_id=ws_a_id, query="the query", limit=10, provider=provider, document_ids=[org_b_doc_id],
    )

    assert matches == []

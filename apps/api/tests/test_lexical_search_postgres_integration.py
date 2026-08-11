"""Production-path integration tests for app.services.lexical_search's real
PostgreSQL full-text branch (`_search_postgresql` - websearch_to_tsquery/
to_tsvector/ts_rank_cd), mirroring
tests/test_vector_search_postgres_integration.py's structure/fixtures
exactly (same POSTGRES_TEST_DATABASE_URL skip-if-unreachable guard, same
schema-via-Base.metadata approach rather than Alembic migrations, same
shared-module-scoped-engine-with-reset isolation strategy - see that file's
module docstring for the full rationale, not repeated here).

Schema is created via Base.metadata.create_all(), not the
0021_lexical_search_index migration, so the GIN functional index itself is
not exercised here (it is a pure performance index - the underlying
to_tsvector/websearch_to_tsquery SQL is correct with or without it). Run via
`npm run api:test:postgres`.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.lexical_search import search_lexical_chunks

POSTGRES_TEST_DATABASE_URL = os.environ.get(
    "POSTGRES_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb_test",
)


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
        "Postgres integration tier requires a reachable server - run "
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
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def db(pg_engine) -> Session:
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    yield session
    session.close()


def _seed_tenant(db: Session, *, suffix: str) -> tuple[str, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"pg-lex-org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"pg-lex-workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"pg-lex-owner-{suffix}@example.test", full_name="Owner")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    db.add_all([organisation, workspace, user, membership])
    db.commit()
    return organisation.id, workspace.id


def _seed_chunk(
    db: Session, *, organisation_id: str, workspace_id: str, key: str, content: str, document_status: str = "ready",
) -> tuple[str, str]:
    document = Document(
        organisation_id=organisation_id, workspace_id=workspace_id, title=key, source_type="txt",
        source_key=f"{key}.txt", status=document_status,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id,
        version_number=1, checksum=f"checksum-{key}", processing_status="ready",
    )
    db.add(version)
    db.flush()
    document.active_document_version_id = version.id
    chunk = Chunk(
        organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
        chunk_index=0, content=content, content_hash=f"hash-{key}", token_count=len(content.split()),
        source_type="txt", source_title=key, status="ready",
    )
    db.add(chunk)
    db.commit()
    return document.id, chunk.id


def test_exact_term_retrieval_via_websearch_to_tsquery(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="exact")
    matching_doc_id, _ = _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="match", content="The error code is E-40921 when the token expires.")
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="other", content="This paragraph is about something else entirely.")

    matches = search_lexical_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="E-40921", limit=10)

    assert len(matches) == 1
    assert matches[0].document_id == matching_doc_id


def test_ranking_prefers_denser_term_match(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="ranking")
    strong_doc_id, _ = _seed_chunk(
        db, organisation_id=organisation_id, workspace_id=workspace_id, key="strong",
        content="refund refund refund policy explains the refund process in detail.",
    )
    weak_doc_id, _ = _seed_chunk(
        db, organisation_id=organisation_id, workspace_id=workspace_id, key="weak",
        content="This document mentions a refund exactly once in passing.",
    )

    matches = search_lexical_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="refund", limit=10)

    assert [m.document_id for m in matches] == [strong_doc_id, weak_doc_id]


def test_organisation_isolation(db: Session) -> None:
    org_a, workspace_a = _seed_tenant(db, suffix="org-a")
    org_b, workspace_b = _seed_tenant(db, suffix="org-b")
    _seed_chunk(db, organisation_id=org_a, workspace_id=workspace_a, key="a", content="the confidential onboarding checklist")
    _seed_chunk(db, organisation_id=org_b, workspace_id=workspace_b, key="b", content="the confidential onboarding checklist")

    matches = search_lexical_chunks(db, organisation_id=org_a, workspace_id=workspace_a, query="confidential onboarding checklist", limit=10)

    assert len(matches) == 1


def test_document_ids_empty_list_means_zero_results(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="scope-empty")
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="rate limit exceeded error code")

    matches = search_lexical_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="rate limit exceeded", limit=10, document_ids=[])

    assert matches == []


@pytest.mark.parametrize("status", ["uploaded", "processing", "failed", "expired", "deleted", "archived"])
def test_non_ready_document_statuses_are_excluded(db: Session, status: str) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix=f"status-{status}")
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="incident postmortem template", document_status=status)

    matches = search_lexical_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="incident postmortem template", limit=10)

    assert matches == []


def test_empty_query_returns_no_matches(db: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db, suffix="empty-query")
    _seed_chunk(db, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="some content here")

    matches = search_lexical_chunks(db, organisation_id=organisation_id, workspace_id=workspace_id, query="   ", limit=10)

    assert matches == []

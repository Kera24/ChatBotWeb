"""Unit tests for app.services.lexical_search's SQLite fallback path
(_search_sqlite - exercised via the default in-memory engine every other unit
test in this suite uses, mirroring test_vector_search_document_status.py's
fixture/seeding shape exactly). The real Postgres full-text path
(_search_postgresql) is covered separately in
test_lexical_search_postgres_integration.py."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.services.lexical_search import search_lexical_chunks


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _seed_tenant(db: Session, *, suffix: str) -> tuple[str, str]:
    organisation = Organisation(name=f"Org {suffix}", slug=f"org-{suffix}", status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Workspace", slug=f"workspace-{suffix}", status="active", default_language="en")
    user = User(email=f"owner-{suffix}@example.test", full_name="Owner")
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


def test_exact_term_retrieval_finds_matching_chunk(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="exact")
    matching_doc_id, _ = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="match", content="The SKU for the widget is ZX-4471-Q.")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="other", content="This document discusses unrelated shipping policy details.")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="ZX-4471-Q", limit=10)

    assert len(matches) == 1
    assert matches[0].document_id == matching_doc_id


def test_no_token_overlap_returns_no_matches(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="no-overlap")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="Refund requests are processed within seven business days.")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="quantum photon entanglement", limit=10)

    assert matches == []


def test_organisation_isolation(db_session: Session) -> None:
    org_a, workspace_a = _seed_tenant(db_session, suffix="org-a")
    org_b, workspace_b = _seed_tenant(db_session, suffix="org-b")
    _seed_chunk(db_session, organisation_id=org_a, workspace_id=workspace_a, key="a", content="the secret onboarding checklist")
    _seed_chunk(db_session, organisation_id=org_b, workspace_id=workspace_b, key="b", content="the secret onboarding checklist")

    matches = search_lexical_chunks(db_session, organisation_id=org_a, workspace_id=workspace_a, query="secret onboarding checklist", limit=10)

    assert len(matches) == 1
    assert matches[0].document_id != ""


def test_workspace_isolation_within_same_organisation(db_session: Session) -> None:
    organisation = Organisation(name="Shared Org", slug="shared-org", status="active", plan_key="starter")
    workspace_one = Workspace(organisation=organisation, name="Workspace One", slug="workspace-one", status="active", default_language="en")
    workspace_two = Workspace(organisation=organisation, name="Workspace Two", slug="workspace-two", status="active", default_language="en")
    db_session.add_all([organisation, workspace_one, workspace_two])
    db_session.commit()

    _seed_chunk(db_session, organisation_id=organisation.id, workspace_id=workspace_one.id, key="one", content="quarterly compliance audit checklist")
    _seed_chunk(db_session, organisation_id=organisation.id, workspace_id=workspace_two.id, key="two", content="quarterly compliance audit checklist")

    matches = search_lexical_chunks(db_session, organisation_id=organisation.id, workspace_id=workspace_one.id, query="quarterly compliance audit", limit=10)

    assert len(matches) == 1


def test_document_ids_none_means_unrestricted(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="scope-none")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="rate limit exceeded error code")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="rate limit exceeded", limit=10, document_ids=None)

    assert len(matches) == 1


def test_document_ids_empty_list_means_zero_results(db_session: Session) -> None:
    """Security-critical: an assistant resolved to an explicitly empty
    knowledge scope must retrieve zero chunks, never fall back to
    "everything" - the same invariant app.services.vector_search enforces."""
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="scope-empty")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="rate limit exceeded error code")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="rate limit exceeded", limit=10, document_ids=[])

    assert matches == []


def test_document_ids_scopes_to_named_documents(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="scope-named")
    included_doc_id, _ = _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="included", content="password reset link expiry policy")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="excluded", content="password reset link expiry policy")

    matches = search_lexical_chunks(
        db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="password reset link", limit=10, document_ids=[included_doc_id],
    )

    assert len(matches) == 1
    assert matches[0].document_id == included_doc_id


@pytest.mark.parametrize("status", ["uploaded", "processing", "failed", "expired", "deleted", "archived"])
def test_non_ready_document_statuses_are_excluded(db_session: Session, status: str) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix=f"status-{status}")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="incident postmortem template", document_status=status)

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="incident postmortem template", limit=10)

    assert matches == []


def test_empty_query_returns_no_matches(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="empty-query")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="doc", content="some content here")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="   ", limit=10)

    assert matches == []


def test_result_is_deterministic_across_repeated_calls(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="deterministic")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="one", content="build pipeline configuration reference")
    _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key="two", content="build pipeline configuration guide")

    first = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="build pipeline configuration", limit=10)
    second = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="build pipeline configuration", limit=10)

    assert [m.chunk_id for m in first] == [m.chunk_id for m in second]


def test_limit_is_respected(db_session: Session) -> None:
    organisation_id, workspace_id = _seed_tenant(db_session, suffix="limit")
    for index in range(5):
        _seed_chunk(db_session, organisation_id=organisation_id, workspace_id=workspace_id, key=f"doc-{index}", content="shared keyword term appears here")

    matches = search_lexical_chunks(db_session, organisation_id=organisation_id, workspace_id=workspace_id, query="shared keyword term", limit=2)

    assert len(matches) == 2

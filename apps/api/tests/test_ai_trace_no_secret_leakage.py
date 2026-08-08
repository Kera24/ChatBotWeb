from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.db.models.ai_trace import AIGuardrailTrace, AIModelCallTrace, AIRetrievalTrace, AITrace, AITraceStage
from app.db.session import get_db
from app.main import create_app

_SECRET_STRIPE_KEY = "".join(("sk", "_live_", "abcdefghij1234567890"))
_SECRET_DB_URL = "postgres://produser:hunter2@prod-db.internal:5432/appdb"


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    original_provider = settings.EMBEDDING_PROVIDER
    original_model = settings.EMBEDDING_MODEL
    original_dimension = settings.EMBEDDING_DIMENSION
    original_chunks = settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
    original_chars = settings.RETRIEVAL_MAX_CONTEXT_CHARS
    original_content_mode = settings.AI_TRACE_CONTENT_MODE
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "leak-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", 5)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", 4000)
    # redacted_preview (rather than the metadata_only default) so this test
    # actually exercises the redaction path end-to-end - metadata_only would
    # trivially "pass" by storing nothing at all.
    object.__setattr__(settings, "AI_TRACE_CONTENT_MODE", "redacted_preview")

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    object.__setattr__(settings, "EMBEDDING_PROVIDER", original_provider)
    object.__setattr__(settings, "EMBEDDING_MODEL", original_model)
    object.__setattr__(settings, "EMBEDDING_DIMENSION", original_dimension)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", original_chunks)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", original_chars)
    object.__setattr__(settings, "AI_TRACE_CONTENT_MODE", original_content_mode)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str, role: str) -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient) -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        organisation = Organisation(name="Leak Test Org", slug="leak-test-org")
        user = User(email="viewer@example.test")
        workspace = Workspace(organisation=organisation, name="Knowledge Base", slug="leak-test-kb")
        membership = Membership(organisation=organisation, user=user, role="viewer")
        db.add_all([organisation, user, workspace, membership])
        db.commit()
        return organisation.id, workspace.id


def add_embedded_chunk(client: TestClient, *, organisation_id: str, workspace_id: str, content: str, title: str) -> None:
    with client.app.state.testing_session() as db:
        document = Document(organisation_id=organisation_id, workspace_id=workspace_id, title=title, source_type="txt", source_key=f"{title}.txt", status="ready")
        db.add(document)
        db.flush()
        version = DocumentVersion(organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, version_number=1, checksum=f"checksum-{title}", processing_status="ready")
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        chunk = Chunk(
            organisation_id=organisation_id, workspace_id=workspace_id, document_id=document.id, document_version_id=version.id,
            chunk_index=0, content=content, content_hash=f"hash-{title}", token_count=len(content.split()),
            source_type="txt", source_title=title, status="ready", embedding_provider="local-mock", embedding_model="leak-test",
            embedding_dimension=8, embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()


def test_secrets_embedded_in_retrieved_documents_never_appear_unredacted_in_any_trace_table(client: TestClient) -> None:
    """Feeds a document whose content contains a live-looking Stripe secret
    key and a database connection string with an embedded password through
    the full RAGOrchestrator.answer() pipeline, then scans every text/JSON
    column on all 5 AI trace tables for the raw secret values."""
    organisation_id, workspace_id = seed_tenant(client)
    add_embedded_chunk(
        client, organisation_id=organisation_id, workspace_id=workspace_id,
        content=f"Internal runbook: rotate {_SECRET_STRIPE_KEY} and the database at {_SECRET_DB_URL} every quarter.",
        title="Internal Runbook",
    )

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/rag/answer",
        params={"organisation_id": organisation_id},
        json={"query": f"Internal runbook: rotate {_SECRET_STRIPE_KEY} and the database at {_SECRET_DB_URL} every quarter."},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    trace_id = response.json()["data"]["trace_id"]

    with client.app.state.testing_session() as db:
        trace = db.query(AITrace).filter_by(trace_id=trace_id).one()
        all_rows = (
            [trace]
            + db.query(AITraceStage).filter_by(trace_id=trace.id).all()
            + db.query(AIRetrievalTrace).filter_by(trace_id=trace.id).all()
            + db.query(AIModelCallTrace).filter_by(trace_id=trace.id).all()
            + db.query(AIGuardrailTrace).filter_by(trace_id=trace.id).all()
        )
        # At least the retrieval preview must have been populated (proves
        # the redaction path actually ran, not just an empty/no-op check).
        retrieval_rows = db.query(AIRetrievalTrace).filter_by(trace_id=trace.id).all()
        assert any(row.content_preview for row in retrieval_rows)

        for row in all_rows:
            for column in row.__table__.columns:
                value = getattr(row, column.name)
                rendered = str(value)
                assert _SECRET_STRIPE_KEY not in rendered, f"Stripe secret leaked in {row.__class__.__name__}.{column.name}"
                assert "hunter2" not in rendered, f"DB password leaked in {row.__class__.__name__}.{column.name}"

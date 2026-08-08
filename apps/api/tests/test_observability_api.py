from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


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
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "obs-api-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHUNKS", 5)
    object.__setattr__(settings, "RETRIEVAL_MAX_CONTEXT_CHARS", 1000)

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
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str, role: str) -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient, *, organisation_name: str, organisation_slug: str, user_email: str, role: str) -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        organisation = Organisation(name=organisation_name, slug=organisation_slug)
        user = User(email=user_email)
        workspace = Workspace(organisation=organisation, name="Knowledge Base", slug=f"{organisation_slug}-knowledge")
        membership = Membership(organisation=organisation, user=user, role=role)
        db.add_all([organisation, user, workspace, membership])
        db.commit()
        return organisation.id, workspace.id, user.id


def add_embedded_chunk(client: TestClient, *, organisation_id: str, workspace_id: str, content: str, title: str) -> str:
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
            source_type="txt", source_title=title, status="ready", embedding_provider="local-mock", embedding_model="obs-api-test",
            embedding_dimension=8, embedding_created_at=datetime.now(timezone.utc),
        )
        db.add(chunk)
        db.commit()
        return chunk.id


def rag_answer(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, role: str, query: str) -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/rag/answer",
        params={"organisation_id": organisation_id},
        json={"query": query},
        headers=dev_headers(email, role),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _seed_answered_trace(client: TestClient) -> tuple[str, str, str]:
    organisation_id, workspace_id, _user_id = seed_tenant(client, organisation_name="Alpha", organisation_slug="alpha-obs", user_email="viewer@example.test", role="viewer")
    add_embedded_chunk(client, organisation_id=organisation_id, workspace_id=workspace_id, content="applications close in december", title="Handbook")
    data = rag_answer(client, organisation_id=organisation_id, workspace_id=workspace_id, email="viewer@example.test", role="viewer", query="applications close in december")
    return organisation_id, workspace_id, data["trace_id"]


def test_list_traces_returns_the_recorded_trace(client: TestClient) -> None:
    organisation_id, workspace_id, trace_id = _seed_answered_trace(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/traces",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["trace_id"] == trace_id
    assert body["data"][0]["answer_state"] == "answered"


def test_get_trace_detail_includes_stages_and_omits_content_by_default(client: TestClient) -> None:
    organisation_id, workspace_id, trace_id = _seed_answered_trace(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/traces/{trace_id}",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["trace_id"] == trace_id
    assert len(data["stages"]) > 0
    assert len(data["model_calls"]) == 1
    assert len(data["guardrails"]) > 0
    # metadata_only is the default retention mode - no content anywhere.
    assert data["model_calls"][0]["raw_prompt_preview"] is None
    assert data["retrieval"][0]["content_preview"] is None


def test_get_trace_detail_include_content_requires_operator_role(client: TestClient) -> None:
    organisation_id, workspace_id, trace_id = _seed_answered_trace(client)

    viewer_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/traces/{trace_id}",
        params={"organisation_id": organisation_id, "include_content": "true"},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert viewer_response.status_code == 403

    with client.app.state.testing_session() as db:
        admin = User(email="admin@example.test")
        db.add(admin)
        db.flush()
        from app.db.models import Membership as MembershipModel

        db.add(MembershipModel(organisation_id=organisation_id, user_id=admin.id, role="org_owner"))
        db.commit()

    admin_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/traces/{trace_id}",
        params={"organisation_id": organisation_id, "include_content": "true"},
        headers=dev_headers("admin@example.test", "org_owner"),
    )
    assert admin_response.status_code == 200


def test_get_trace_detail_returns_404_for_cross_tenant_trace_id(client: TestClient) -> None:
    _organisation_id, _workspace_id, trace_id = _seed_answered_trace(client)
    other_org_id, other_workspace_id, _user_id = seed_tenant(client, organisation_name="Beta", organisation_slug="beta-obs", user_email="beta-viewer@example.test", role="viewer")

    response = client.get(
        f"/api/v1/workspaces/{other_workspace_id}/observability/traces/{trace_id}",
        params={"organisation_id": other_org_id},
        headers=dev_headers("beta-viewer@example.test", "viewer"),
    )
    assert response.status_code == 404


def test_metrics_endpoint_reflects_the_answered_trace(client: TestClient) -> None:
    organisation_id, workspace_id, _trace_id = _seed_answered_trace(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/metrics",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["request_volume"] == 1
    assert data["answered_count"] == 1
    assert data["fallback_rate"] == 0.0
    assert data["total_tokens"] > 0


def test_anomalies_endpoint_returns_deterministic_signals(client: TestClient) -> None:
    organisation_id, workspace_id, _trace_id = _seed_answered_trace(client)

    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/anomalies",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    metrics = {signal["metric"] for signal in data}
    assert "fallback_rate" in metrics
    assert "p95_latency_ms" in metrics


def test_alerts_endpoint_requires_operator_role_not_viewer(client: TestClient) -> None:
    organisation_id, workspace_id, _trace_id = _seed_answered_trace(client)

    viewer_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/alerts",
        params={"organisation_id": organisation_id},
        headers=dev_headers("viewer@example.test", "viewer"),
    )
    assert viewer_response.status_code == 403

    with client.app.state.testing_session() as db:
        admin = User(email="admin2@example.test")
        db.add(admin)
        db.flush()
        from app.db.models import Membership as MembershipModel

        db.add(MembershipModel(organisation_id=organisation_id, user_id=admin.id, role="client_admin"))
        db.commit()

    admin_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/observability/alerts",
        params={"organisation_id": organisation_id},
        headers=dev_headers("admin2@example.test", "client_admin"),
    )
    assert admin_response.status_code == 200


def test_list_traces_never_returns_another_organisations_traces(client: TestClient) -> None:
    organisation_id, workspace_id, trace_id = _seed_answered_trace(client)
    other_org_id, other_workspace_id, _user_id = seed_tenant(client, organisation_name="Gamma", organisation_slug="gamma-obs", user_email="gamma-viewer@example.test", role="viewer")

    response = client.get(
        f"/api/v1/workspaces/{other_workspace_id}/observability/traces",
        params={"organisation_id": other_org_id},
        headers=dev_headers("gamma-viewer@example.test", "viewer"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 0
    assert body["data"] == []

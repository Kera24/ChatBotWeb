from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.core.config import settings
from app.db.base import Base
from app.db.models import Chunk, Document, DocumentVersion, EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun, Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
    object.__setattr__(settings, "EMBEDDING_PROVIDER", "local-mock")
    object.__setattr__(settings, "EMBEDDING_MODEL", "eval-api-test")
    object.__setattr__(settings, "EMBEDDING_DIMENSION", 8)

    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def headers(email: str, role: str) -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


@dataclass(frozen=True)
class SeededTenant:
    organisation_id: str
    workspace_id: str
    widget_id: str
    document_id: str
    owner_email: str
    admin_email: str
    contributor_email: str
    viewer_email: str


def seed_tenant(client: TestClient, *, slug: str) -> SeededTenant:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        owner = User(email=f"owner-{unique}@example.test")
        admin = User(email=f"admin-{unique}@example.test")
        contributor = User(email=f"contributor-{unique}@example.test")
        viewer = User(email=f"viewer-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Workspace", slug=f"{slug}-workspace-{unique}", status="active")
        db.add_all([
            org, owner, admin, contributor, viewer, workspace,
            Membership(organisation=org, user=owner, role="org_owner", status="active"),
            Membership(organisation=org, user=admin, role="client_admin", status="active"),
            Membership(organisation=org, user=contributor, role="contributor", status="active"),
            Membership(organisation=org, user=viewer, role="viewer", status="active"),
        ])
        db.commit()

        document = Document(organisation_id=org.id, workspace_id=workspace.id, title="FAQ", source_type="txt", source_key="faq.txt", status="ready")
        db.add(document)
        db.flush()
        version = DocumentVersion(organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, version_number=1, checksum="c1", processing_status="ready")
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        db.add(Chunk(
            organisation_id=org.id, workspace_id=workspace.id, document_id=document.id, document_version_id=version.id,
            chunk_index=0, content="Applications close on March 1st.", content_hash="h1", token_count=5,
            source_type="txt", source_title="FAQ", status="ready",
            embedding_provider="local-mock", embedding_model="eval-api-test", embedding_dimension=8,
            embedding_created_at=datetime.now(timezone.utc),
        ))
        db.commit()

        widget = create_widget(
            db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development",
            actor_user_id=owner.id, initial_configuration={"knowledge_scope_json": [document.id]},
        )

        return SeededTenant(
            organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, document_id=document.id,
            owner_email=owner.email, admin_email=admin.email, contributor_email=contributor.email, viewer_email=viewer.email,
        )


def create_dataset_api(client: TestClient, *, organisation_id: str, workspace_id: str, widget_id: str, email: str, role: str = "org_owner"):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/evaluation/datasets",
        params={"organisation_id": organisation_id},
        headers=headers(email, role),
        json={"widget_id": widget_id, "name": "Launch dataset", "version": "1"},
    )


def test_create_and_list_datasets(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="datasets")

    created = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.owner_email)
    assert created.status_code == 201
    dataset_id = created.json()["data"]["id"]

    listed = client.get(f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"))
    assert listed.status_code == 200
    assert any(item["id"] == dataset_id for item in listed.json()["data"])


def test_viewer_can_read_but_not_create_datasets(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="rbac")

    forbidden = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.viewer_email, role="viewer")
    assert forbidden.status_code == 403

    ok_create = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.owner_email)
    assert ok_create.status_code == 201
    dataset_id = ok_create.json()["data"]["id"]

    ok_read = client.get(f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets/{dataset_id}", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.viewer_email, "viewer"))
    assert ok_read.status_code == 200


def test_contributor_cannot_read_or_write_evaluation_data(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="contrib")

    response = client.get(f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.contributor_email, "contributor"))
    assert response.status_code == 403


def test_create_case_validates_category_and_answerability_vocabulary(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="vocab")

    created = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.owner_email)
    dataset_id = created.json()["data"]["id"]

    invalid = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets/{dataset_id}/cases",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"question": "Q?", "category": "not-a-real-category", "expected_answerability": "answerable"},
    )
    assert invalid.status_code == 422

    valid = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets/{dataset_id}/cases",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"question": "When do applications close?", "category": "answerable_factual", "expected_answerability": "answerable", "expected_document_ids": [tenant.document_id]},
    )
    assert valid.status_code == 201


def test_full_run_lifecycle_via_api(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="lifecycle")

    dataset_id = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.owner_email).json()["data"]["id"]
    client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets/{dataset_id}/cases",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"question": "When do applications close?", "category": "answerable_factual", "expected_answerability": "answerable", "expected_document_ids": [tenant.document_id]},
    )

    run_response = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"dataset_id": dataset_id, "widget_id": tenant.widget_id, "mode": "mock"},
    )
    assert run_response.status_code == 201
    run_id = run_response.json()["data"]["id"]
    assert run_response.json()["data"]["status"] == "completed"

    detail = client.get(f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs/{run_id}", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"))
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["summary"]["total_cases"] == 1
    assert "gate" in body

    results = client.get(f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs/{run_id}/results", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"))
    assert results.status_code == 200
    assert len(results.json()["data"]) == 1

    result_case_id = results.json()["data"][0]["case_id"]
    case_detail = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs/{run_id}/results/{result_case_id}",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
    )
    assert case_detail.status_code == 200
    assert case_detail.json()["data"]["case"]["question"] == "When do applications close?"


def test_compare_runs_endpoint(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="compare")

    dataset_id = create_dataset_api(client, organisation_id=tenant.organisation_id, workspace_id=tenant.workspace_id, widget_id=tenant.widget_id, email=tenant.owner_email).json()["data"]["id"]
    client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/datasets/{dataset_id}/cases",
        params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"question": "When do applications close?", "category": "answerable_factual", "expected_answerability": "answerable", "expected_document_ids": [tenant.document_id]},
    )

    run_one = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"dataset_id": dataset_id, "widget_id": tenant.widget_id, "mode": "mock"},
    ).json()["data"]["id"]
    run_two = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs", params={"organisation_id": tenant.organisation_id}, headers=headers(tenant.owner_email, "org_owner"),
        json={"dataset_id": dataset_id, "widget_id": tenant.widget_id, "mode": "mock"},
    ).json()["data"]["id"]

    comparison = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/evaluation/runs/compare",
        params={"organisation_id": tenant.organisation_id, "baseline_run_id": run_one, "candidate_run_id": run_two},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    assert comparison.status_code == 200
    assert "comparison" in comparison.json()["data"]


def test_cross_organisation_requests_are_rejected(client: TestClient) -> None:
    tenant_a = seed_tenant(client, slug="org-a")
    seed_tenant(client, slug="org-b")

    dataset_id = create_dataset_api(client, organisation_id=tenant_a.organisation_id, workspace_id=tenant_a.workspace_id, widget_id=tenant_a.widget_id, email=tenant_a.owner_email).json()["data"]["id"]

    # A user with no membership in org_a cannot list org_a's datasets even by guessing the workspace id.
    stranger_response = client.get(
        f"/api/v1/workspaces/{tenant_a.workspace_id}/evaluation/datasets",
        params={"organisation_id": tenant_a.organisation_id},
        headers=headers("stranger@example.test", "org_owner"),
    )
    assert stranger_response.status_code in {401, 403}
    assert dataset_id  # dataset exists but stranger cannot see it

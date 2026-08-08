from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.widget_admin.service import create_widget
from app.db.base import Base
from app.db.models import Membership, Organisation, User, Workspace
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def client() -> TestClient:
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
    owner_email: str
    viewer_email: str


def seed_tenant(client: TestClient, *, slug: str) -> SeededTenant:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        owner = User(email=f"owner-{unique}@example.test")
        viewer = User(email=f"viewer-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Workspace", slug=f"{slug}-workspace-{unique}", status="active")
        db.add_all([
            org, owner, viewer, workspace,
            Membership(organisation=org, user=owner, role="org_owner", status="active"),
            Membership(organisation=org, user=viewer, role="viewer", status="active"),
        ])
        db.commit()
        widget = create_widget(db, organisation_id=org.id, workspace_id=workspace.id, display_name="Assistant", environment="development", actor_user_id=owner.id)
        return SeededTenant(organisation_id=org.id, workspace_id=workspace.id, widget_id=widget.id, owner_email=owner.email, viewer_email=viewer.email)


def test_list_templates_always_includes_platform_core(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="templates")
    response = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    assert response.status_code == 200
    layers = {item["layer"] for item in response.json()["data"]}
    assert "platform_core" in layers


def test_viewer_can_read_but_not_create_templates(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="rbac")
    forbidden = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.viewer_email, "viewer"),
        json={"layer": "assistant_persona_tone", "name": "Persona"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"layer": "assistant_persona_tone", "name": "Persona"},
    )
    assert allowed.status_code == 201


def test_cannot_create_platform_immutable_template_via_workspace_endpoint(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="immutable")
    response = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"layer": "platform_core", "name": "Nice try"},
    )
    assert response.status_code == 400


def test_org_owner_cannot_see_full_platform_content_only_summary(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="redaction")
    listed = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    platform_entry = next(item for item in listed.json()["data"] if item["layer"] == "platform_core")
    assert platform_entry["content_visibility"] == "summary_only"
    assert "content" not in platform_entry  # safe_template_summary never includes raw content at all

    template_id = platform_entry["id"]
    versions = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates/{template_id}/versions",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
    ).json()["data"]
    assert versions[0]["content_visibility"] == "summary_only"
    assert versions[0]["content"] is None

    super_admin_versions = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates/{template_id}/versions",
        params={"organisation_id": tenant.organisation_id},
        headers=headers("super@example.test", "super_admin"),
    ).json()["data"]
    assert super_admin_versions[0]["content_visibility"] == "full"
    assert super_admin_versions[0]["content"] is not None


def test_full_draft_to_deploy_lifecycle_via_api(client: TestClient) -> None:
    tenant = seed_tenant(client, slug="lifecycle")
    create_template = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"layer": "assistant_persona_tone", "name": "Persona"},
    )
    template_id = create_template.json()["data"]["id"]

    draft = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/templates/{template_id}/versions",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"content": "Be warm and concise.", "change_notes": "initial"},
    )
    assert draft.status_code == 201
    version_id = draft.json()["data"]["id"]
    assert draft.json()["data"]["status"] == "draft"

    under_eval = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/versions/{version_id}/transition",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"new_status": "under_evaluation"},
    )
    assert under_eval.status_code == 200

    approved = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/versions/{version_id}/transition",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"new_status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    deployed = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/deployments",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={"version_id": version_id, "widget_id": tenant.widget_id},
    )
    assert deployed.status_code == 201
    deployment_id = deployed.json()["data"]["id"]
    assert deployed.json()["data"]["active_version_id"] == version_id

    current = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/deployments",
        params={"organisation_id": tenant.organisation_id, "layer": "assistant_persona_tone", "widget_id": tenant.widget_id},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    assert current.json()["data"]["active_version_id"] == version_id

    preview = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/preview",
        params={"organisation_id": tenant.organisation_id, "widget_id": tenant.widget_id},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["engaged"] is True
    assert "Be warm and concise." in preview.json()["data"]["system_prompt"]

    audit = client.get(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/audit-events",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
    )
    actions = {event["action"] for event in audit.json()["data"]}
    assert "deployed" in actions

    no_rollback_target = client.post(
        f"/api/v1/workspaces/{tenant.workspace_id}/prompts/deployments/{deployment_id}/rollback",
        params={"organisation_id": tenant.organisation_id},
        headers=headers(tenant.owner_email, "org_owner"),
        json={},
    )
    assert no_rollback_target.status_code == 400


def test_cross_tenant_template_access_is_404(client: TestClient) -> None:
    tenant_a = seed_tenant(client, slug="tenant-a")
    tenant_b = seed_tenant(client, slug="tenant-b")

    created = client.post(
        f"/api/v1/workspaces/{tenant_a.workspace_id}/prompts/templates",
        params={"organisation_id": tenant_a.organisation_id},
        headers=headers(tenant_a.owner_email, "org_owner"),
        json={"layer": "organisation_guidance", "name": "Guidance"},
    )
    template_id = created.json()["data"]["id"]

    cross_tenant = client.get(
        f"/api/v1/workspaces/{tenant_b.workspace_id}/prompts/templates/{template_id}",
        params={"organisation_id": tenant_b.organisation_id},
        headers=headers(tenant_b.owner_email, "org_owner"),
    )
    assert cross_tenant.status_code == 404

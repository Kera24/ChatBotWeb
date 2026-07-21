from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    AuditEvent,
    Document,
    DocumentVersion,
    Membership,
    Organisation,
    PublicCredential,
    User,
    WidgetConfigurationRevision,
    Workspace,
)
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


def headers(email: str, role: str = "client_admin") -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


def seed_tenant(client: TestClient, *, slug: str, email: str, role: str = "client_admin") -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        user = User(email=email)
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"{slug}-knowledge-{unique}", status="active")
        membership = Membership(organisation=org, user=user, role=role)
        db.add_all([org, user, workspace, membership])
        db.commit()
        return org.id, workspace.id, user.id


def create_widget(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, display_name: str = "Admissions Widget") -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={
            "display_name": display_name,
            "environment": "development",
            "initial_configuration": {
                "bot_name": display_name,
                "welcome_message": "Ask us about admissions.",
                "launcher_label": "Ask us",
                "primary_colour": "#111827",
                "suggested_questions_json": ["How do I apply?"],
                "max_initial_suggestions": 1,
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def add_origin(client: TestClient, *, organisation_id: str, workspace_id: str, widget_id: str, email: str, origin: str = "http://localhost:3000") -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets/{widget_id}/origins",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={"origin": origin},
    )
    assert response.status_code == 201
    return response.json()["data"]


def activate_key(client: TestClient, *, organisation_id: str, workspace_id: str, credential_id: str, email: str) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate",
        params={"organisation_id": organisation_id},
        headers=headers(email),
    )
    assert response.status_code == 200


def get_draft(client: TestClient, *, organisation_id: str, workspace_id: str, widget_id: str, email: str) -> dict:
    response = client.get(
        f"/api/v1/workspaces/{workspace_id}/widgets/{widget_id}/draft",
        params={"organisation_id": organisation_id},
        headers=headers(email),
    )
    assert response.status_code == 200
    return response.json()["data"]


def publish_current_draft(client: TestClient, *, organisation_id: str, workspace_id: str, widget: dict, email: str) -> dict:
    draft = get_draft(client, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget["id"], email=email)
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/publish",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={"draft_revision_id": draft["id"], "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert response.status_code == 200
    return response.json()["data"]


def seed_document(client: TestClient, *, organisation_id: str, workspace_id: str, title: str, status: str = "ready", processing_status: str = "ready") -> str:
    with client.app.state.testing_session() as db:
        document = Document(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            title=title,
            source_type="synthetic",
            source_key=f"synthetic-{uuid4().hex}",
            status=status,
            visibility="workspace",
        )
        db.add(document)
        db.flush()
        version = DocumentVersion(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document.id,
            version_number=1,
            checksum=uuid4().hex,
            processing_status=processing_status,
        )
        db.add(version)
        db.flush()
        document.active_document_version_id = version.id
        db.commit()
        return document.id


def public_config(client: TestClient, public_key: str, *, origin: str = "http://localhost:3000", etag: str | None = None) -> TestClient:
    request_headers = {"Origin": origin, "X-Request-ID": "req-admin-b5", "X-Widget-SDK-Version": "0.1.0-foundation.0", "X-Widget-Protocol-Major": "1"}
    if etag:
        request_headers["If-None-Match"] = etag
    return client.get(f"/api/v1/widget/{public_key}/config", headers=request_headers)


def test_widget_admin_b5_cross_tenant_and_viewer_route_denial(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="alpha-b5", email="alpha-b5@example.test")
    org_b, workspace_b, _ = seed_tenant(client, slug="beta-b5", email="beta-b5@example.test")
    viewer_org, viewer_workspace, _ = seed_tenant(client, slug="viewer-b5", email="viewer-b5@example.test", role="viewer")
    alpha = create_widget(client, organisation_id=org_a, workspace_id=workspace_a, email="alpha-b5@example.test")
    beta = create_widget(client, organisation_id=org_b, workspace_id=workspace_b, email="beta-b5@example.test")

    cross_routes = [
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/draft"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/origins"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/embed"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/knowledge-options"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/revisions"),
        ("get", f"/api/v1/workspaces/{workspace_b}/widgets/{alpha['id']}/installation-status"),
    ]
    for method, path in cross_routes:
        response = getattr(client, method)(path, params={"organisation_id": org_b}, headers=headers("beta-b5@example.test"))
        assert response.status_code == 404

    viewer_attempts = [
        client.get(f"/api/v1/workspaces/{workspace_a}/widgets/{alpha['id']}", params={"organisation_id": org_a}, headers=headers("viewer-b5@example.test", "viewer")),
        client.post(f"/api/v1/workspaces/{viewer_workspace}/widgets", params={"organisation_id": viewer_org}, headers=headers("viewer-b5@example.test", "viewer"), json={"display_name": "Blocked"}),
        client.post(f"/api/v1/workspaces/{workspace_b}/widgets/{beta['id']}/rotate-key", params={"organisation_id": org_b}, headers=headers("viewer-b5@example.test", "viewer"), json={"expected_public_credential_id": beta["public_credential_id"]}),
    ]
    assert all(response.status_code == 403 for response in viewer_attempts)


def test_widget_admin_b5_publish_and_rollback_concurrency_are_authoritative(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="race-b5", email="race-b5@example.test")
    widget = create_widget(client, organisation_id=org, workspace_id=workspace, email="race-b5@example.test")
    add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="race-b5@example.test")
    activate_key(client, organisation_id=org, workspace_id=workspace, credential_id=widget["public_credential_id"], email="race-b5@example.test")
    draft = get_draft(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="race-b5@example.test")

    changed = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/draft",
        params={"organisation_id": org},
        headers=headers("race-b5@example.test"),
        json={"bot_name": "Race Updated", "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert changed.status_code == 200
    stale_publish = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/publish",
        params={"organisation_id": org},
        headers=headers("race-b5@example.test"),
        json={"draft_revision_id": draft["id"], "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert stale_publish.status_code == 409

    first = publish_current_draft(client, organisation_id=org, workspace_id=workspace, widget=widget, email="race-b5@example.test")
    next_draft = get_draft(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="race-b5@example.test")
    second_change = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/draft",
        params={"organisation_id": org},
        headers=headers("race-b5@example.test"),
        json={"bot_name": "Race Second", "expected_concurrency_version": next_draft["concurrency_version"]},
    )
    assert second_change.status_code == 200
    second = publish_current_draft(client, organisation_id=org, workspace_id=workspace, widget=widget, email="race-b5@example.test")

    stale_rollback = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/rollback",
        params={"organisation_id": org},
        headers=headers("race-b5@example.test"),
        json={"target_revision_id": first["published_revision"]["id"], "expected_active_revision_id": first["published_revision"]["id"]},
    )
    assert stale_rollback.status_code == 409

    no_mutation_route = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/revisions/{second['published_revision']['id']}",
        params={"organisation_id": org},
        headers=headers("race-b5@example.test"),
        json={"bot_name": "Mutated"},
    )
    assert no_mutation_route.status_code == 405


def test_widget_admin_b5_preview_grant_and_knowledge_scope_hardening(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="knowledge-alpha-b5", email="knowledge-alpha-b5@example.test")
    org_b, workspace_b, _ = seed_tenant(client, slug="knowledge-beta-b5", email="knowledge-beta-b5@example.test")
    alpha_doc = seed_document(client, organisation_id=org_a, workspace_id=workspace_a, title="Alpha Observatory Source")
    beta_doc = seed_document(client, organisation_id=org_b, workspace_id=workspace_b, title="Beta Archive Source")
    widget = create_widget(client, organisation_id=org_a, workspace_id=workspace_a, email="knowledge-alpha-b5@example.test")
    draft = get_draft(client, organisation_id=org_a, workspace_id=workspace_a, widget_id=widget["id"], email="knowledge-alpha-b5@example.test")

    cross_scope = client.patch(
        f"/api/v1/workspaces/{workspace_a}/widgets/{widget['id']}/draft/knowledge",
        params={"organisation_id": org_a},
        headers=headers("knowledge-alpha-b5@example.test"),
        json={"document_ids": [beta_doc], "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert cross_scope.status_code == 422

    scoped = client.patch(
        f"/api/v1/workspaces/{workspace_a}/widgets/{widget['id']}/draft/knowledge",
        params={"organisation_id": org_a},
        headers=headers("knowledge-alpha-b5@example.test"),
        json={"document_ids": [alpha_doc], "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert scoped.status_code == 200
    scoped_draft = scoped.json()["data"]

    grant = client.post(
        f"/api/v1/workspaces/{workspace_a}/widgets/{widget['id']}/preview-grant",
        params={"organisation_id": org_a},
        headers=headers("knowledge-alpha-b5@example.test"),
        json={"draft_revision_id": scoped_draft["id"]},
    )
    assert grant.status_code == 200
    preview_token = grant.json()["data"]["preview_token"]
    assert preview_token.startswith("wpg_")
    assert grant.json()["data"]["configuration"]["knowledge_scope_json"] == [alpha_doc]

    cross_grant = client.post(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget['id']}/preview-grant",
        params={"organisation_id": org_b},
        headers=headers("knowledge-beta-b5@example.test"),
        json={"draft_revision_id": scoped_draft["id"]},
    )
    assert cross_grant.status_code == 404

    add_origin(client, organisation_id=org_a, workspace_id=workspace_a, widget_id=widget["id"], email="knowledge-alpha-b5@example.test")
    activate_key(client, organisation_id=org_a, workspace_id=workspace_a, credential_id=widget["public_credential_id"], email="knowledge-alpha-b5@example.test")
    published = publish_current_draft(client, organisation_id=org_a, workspace_id=workspace_a, widget=widget, email="knowledge-alpha-b5@example.test")

    published_preview = client.post(
        f"/api/v1/workspaces/{workspace_a}/widgets/{widget['id']}/preview-grant",
        params={"organisation_id": org_a},
        headers=headers("knowledge-alpha-b5@example.test"),
        json={"draft_revision_id": published["published_revision"]["id"]},
    )
    assert published_preview.status_code == 422

    with client.app.state.testing_session() as db:
        document = db.get(Document, alpha_doc)
        assert document is not None
        document.deleted_at = datetime.now(timezone.utc)
        db.commit()

    current_draft = get_draft(client, organisation_id=org_a, workspace_id=workspace_a, widget_id=widget["id"], email="knowledge-alpha-b5@example.test")
    validation = client.post(
        f"/api/v1/workspaces/{workspace_a}/widgets/{widget['id']}/validate-publish",
        params={"organisation_id": org_a},
        headers=headers("knowledge-alpha-b5@example.test"),
        json={"draft_revision_id": current_draft["id"], "expected_concurrency_version": current_draft["concurrency_version"]},
    )
    assert validation.status_code == 200
    assert any(error["field"] == "knowledge_scope_json" for error in validation.json()["data"]["errors"])

    with client.app.state.testing_session() as db:
        events = list(db.execute(select(AuditEvent)).scalars().all())
        actions = {event.action for event in events}
        assert {"widget_knowledge_scope.changed", "widget.published"}.issubset(actions)
        assert preview_token not in str([event.metadata_json for event in events])
        assert beta_doc not in str([revision.knowledge_scope_json for revision in db.execute(select(WidgetConfigurationRevision)).scalars().all()])


def test_widget_admin_b5_key_rotation_resets_installation_evidence_for_new_key(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="install-b5", email="install-b5@example.test")
    widget = create_widget(client, organisation_id=org, workspace_id=workspace, email="install-b5@example.test")
    add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="install-b5@example.test")
    activate_key(client, organisation_id=org, workspace_id=workspace, credential_id=widget["public_credential_id"], email="install-b5@example.test")
    publish_current_draft(client, organisation_id=org, workspace_id=workspace, widget=widget, email="install-b5@example.test")

    observed = public_config(client, widget["public_identifier"])
    assert observed.status_code == 200
    status_before = client.get(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": org},
        headers=headers("install-b5@example.test"),
    )
    assert status_before.json()["data"][0]["status"] == "observed"
    assert status_before.json()["data"][0]["sdk_version"] == "0.1.0-foundation.0"

    rotation = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/rotate-key",
        params={"organisation_id": org},
        headers=headers("install-b5@example.test"),
        json={"expected_public_credential_id": widget["public_credential_id"]},
    )
    assert rotation.status_code == 200
    new_key = rotation.json()["data"]["public_key"]

    assert public_config(client, widget["public_identifier"]).status_code == 404
    status_after_rotation = client.get(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": org},
        headers=headers("install-b5@example.test"),
    )
    assert status_after_rotation.status_code == 200
    assert status_after_rotation.json()["data"][0]["status"] == "not_observed"

    assert public_config(client, new_key).status_code == 200
    status_after_new_key = client.get(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": org},
        headers=headers("install-b5@example.test"),
    )
    item = status_after_new_key.json()["data"][0]
    assert item["status"] == "observed"
    assert item["protocol_major"] == 1

    with client.app.state.testing_session() as db:
        old = db.execute(select(PublicCredential).where(PublicCredential.public_identifier == widget["public_identifier"])).scalar_one()
        assert old.status == "revoked"
        events = list(db.execute(select(AuditEvent)).scalars().all())
        assert "widget_public_key_rotated" in {event.action for event in events}
        assert widget["public_identifier"] not in str([event.metadata_json for event in events])

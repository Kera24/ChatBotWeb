from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AuditEvent, Membership, Organisation, User, Widget, WidgetConfigurationRevision, Workspace
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


def create_widget_api(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, display_name: str = "Admissions Widget"):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={
            "display_name": display_name,
            "environment": "development",
            "initial_configuration": {
                "bot_name": "Admissions Assistant",
                "welcome_message": "Ask us about admissions.",
                "launcher_label": "Ask us",
                "primary_colour": "#111827",
                "suggested_questions_json": ["How do I apply?"],
                "max_initial_suggestions": 1,
            },
        },
    )


def activate_and_add_origin(client: TestClient, *, organisation_id: str, workspace_id: str, credential_id: str, email: str) -> None:
    origin = client.post(
        f"/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={"origin": "http://localhost:3000"},
    )
    assert origin.status_code == 201
    activated = client.post(
        f"/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate",
        params={"organisation_id": organisation_id},
        headers=headers(email),
    )
    assert activated.status_code == 200


def public_config(client: TestClient, public_identifier: str, *, etag: str | None = None):
    request_headers = {"Origin": "http://localhost:3000", "X-Request-ID": "req-admin-revision"}
    if etag:
        request_headers["If-None-Match"] = etag
    return client.get(f"/api/v1/widget/{public_identifier}/config", headers=request_headers)


def test_widget_draft_publish_public_config_and_rollback_flow(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="admin@example.test")
    created = create_widget_api(client, organisation_id=org, workspace_id=workspace, email="admin@example.test")
    assert created.status_code == 201
    widget = created.json()["data"]
    widget_id = widget["id"]
    credential_id = widget["public_credential_id"]
    public_identifier = widget["public_identifier"]
    draft_id = widget["draft"]["id"]
    draft_version = widget["draft"]["concurrency_version"]

    stale = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/draft",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"bot_name": "Admissions Draft", "expected_concurrency_version": draft_version + 10},
    )
    assert stale.status_code == 409

    updated = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/draft",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"bot_name": "Published Alpha", "expected_concurrency_version": draft_version},
    )
    assert updated.status_code == 200
    updated_draft = updated.json()["data"]
    assert updated_draft["configuration"]["bot_name"] == "Published Alpha"

    blocked_publish = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/publish",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"draft_revision_id": draft_id, "expected_concurrency_version": updated_draft["concurrency_version"]},
    )
    assert blocked_publish.status_code == 422
    assert "allowed_origins" in str(blocked_publish.json())

    activate_and_add_origin(client, organisation_id=org, workspace_id=workspace, credential_id=credential_id, email="admin@example.test")
    published = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/publish",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"draft_revision_id": draft_id, "expected_concurrency_version": updated_draft["concurrency_version"]},
    )
    assert published.status_code == 200
    first_published = published.json()["data"]["published_revision"]
    assert first_published["status"] == "published"
    assert first_published["configuration"]["bot_name"] == "Published Alpha"

    public_first = public_config(client, public_identifier)
    assert public_first.status_code == 200
    assert public_first.json()["widget"]["bot_name"] == "Published Alpha"
    first_etag = public_first.headers["etag"]

    detail = client.get(f"/api/v1/workspaces/{workspace}/widgets/{widget_id}", params={"organisation_id": org}, headers=headers("admin@example.test"))
    next_draft = detail.json()["data"]["draft"]
    private_update = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/draft",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"bot_name": "Private Draft", "expected_concurrency_version": next_draft["concurrency_version"]},
    )
    assert private_update.status_code == 200
    public_after_draft = public_config(client, public_identifier, etag=first_etag)
    assert public_after_draft.status_code == 304

    second_draft = private_update.json()["data"]
    second_publish = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/publish",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"draft_revision_id": second_draft["id"], "expected_concurrency_version": second_draft["concurrency_version"]},
    )
    assert second_publish.status_code == 200
    public_second = public_config(client, public_identifier)
    assert public_second.status_code == 200
    assert public_second.json()["widget"]["bot_name"] == "Private Draft"
    assert public_second.headers["etag"] != first_etag

    rollback = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget_id}/rollback",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={
            "target_revision_id": first_published["id"],
            "expected_active_revision_id": second_publish.json()["data"]["published_revision"]["id"],
        },
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["published_revision"]["source_revision_id"] == first_published["id"]
    public_after_rollback = public_config(client, public_identifier)
    assert public_after_rollback.status_code == 200
    assert public_after_rollback.json()["widget"]["bot_name"] == "Published Alpha"

    with client.app.state.testing_session() as db:
        revisions = db.execute(select(WidgetConfigurationRevision).where(WidgetConfigurationRevision.widget_id == widget_id)).scalars().all()
        revision_numbers = sorted(revision.revision_number for revision in revisions)
        assert revision_numbers == list(range(1, len(revision_numbers) + 1))
        assert len([revision for revision in revisions if revision.status == "published"]) == 3
        assert db.get(Widget, widget_id).active_published_revision_id == rollback.json()["data"]["published_revision"]["id"]
        actions = {event.action for event in db.execute(select(AuditEvent)).scalars().all()}
        assert {"widget.created", "widget_draft.updated", "widget.published", "widget_configuration.rolled_back"}.issubset(actions)


def test_widget_admin_tenant_scope_and_rbac(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="alpha", email="alpha@example.test")
    org_b, workspace_b, _ = seed_tenant(client, slug="beta", email="beta@example.test")
    viewer_org, viewer_workspace, _ = seed_tenant(client, slug="viewer", email="viewer@example.test", role="viewer")
    created = create_widget_api(client, organisation_id=org_a, workspace_id=workspace_a, email="alpha@example.test")
    widget_id = created.json()["data"]["id"]

    denied_create = create_widget_api(client, organisation_id=viewer_org, workspace_id=viewer_workspace, email="viewer@example.test")
    cross_read = client.get(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget_id}",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test"),
    )
    cross_update = client.patch(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget_id}/draft",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test"),
        json={"bot_name": "Stolen", "expected_concurrency_version": 1},
    )
    non_member = client.get(
        f"/api/v1/workspaces/{workspace_a}/widgets",
        params={"organisation_id": org_a},
        headers=headers("viewer@example.test", "viewer"),
    )

    assert denied_create.status_code == 403
    assert cross_read.status_code == 404
    assert cross_update.status_code == 404
    assert non_member.status_code == 403
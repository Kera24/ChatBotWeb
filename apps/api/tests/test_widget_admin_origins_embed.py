from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AuditEvent, Membership, Organisation, PublicCredential, User, Workspace
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


def seed_tenant(client: TestClient, *, slug: str, email: str, role: str = "client_admin") -> tuple[str, str]:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name=f"{slug} Org", slug=f"{slug}-{unique}", status="active")
        user = User(email=email)
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"{slug}-knowledge-{unique}", status="active")
        membership = Membership(organisation=org, user=user, role=role)
        db.add_all([org, user, workspace, membership])
        db.commit()
        return org.id, workspace.id


def create_widget(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, environment: str = "development") -> dict:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={
            "display_name": "Admissions Widget",
            "environment": environment,
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
    assert response.status_code == 201
    return response.json()["data"]


def activate_key(client: TestClient, *, organisation_id: str, workspace_id: str, credential_id: str, email: str) -> None:
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate",
        params={"organisation_id": organisation_id},
        headers=headers(email),
    )
    assert response.status_code == 200


def add_origin(client: TestClient, *, organisation_id: str, workspace_id: str, widget_id: str, email: str, origin: str):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets/{widget_id}/origins",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={"origin": origin},
    )


def publish_widget(client: TestClient, *, organisation_id: str, workspace_id: str, widget: dict, email: str) -> dict:
    draft = client.get(f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/draft", params={"organisation_id": organisation_id}, headers=headers(email)).json()["data"]
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/widgets/{widget['id']}/publish",
        params={"organisation_id": organisation_id},
        headers=headers(email),
        json={"draft_revision_id": draft["id"], "expected_concurrency_version": draft["concurrency_version"]},
    )
    assert response.status_code == 200
    return response.json()["data"]


def public_config(client: TestClient, public_key: str, *, origin: str = "http://localhost:3000", etag: str | None = None):
    request_headers = {"Origin": origin, "X-Request-ID": "req-b2"}
    if etag:
        request_headers["If-None-Match"] = etag
    return client.get(f"/api/v1/widget/{public_key}/config", headers=request_headers)


def test_widget_origin_api_normalises_rejects_duplicates_and_preserves_final_origin(client: TestClient) -> None:
    org, workspace = seed_tenant(client, slug="alpha", email="admin@example.test")
    widget = create_widget(client, organisation_id=org, workspace_id=workspace, email="admin@example.test")

    first = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="http://LOCALHOST:3000/")
    duplicate = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="http://localhost:3000")
    wildcard = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="https://*.example.com")
    path = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="https://example.com/path")

    assert first.status_code == 201
    assert first.json()["data"]["origin"] == "http://localhost:3000"
    assert duplicate.status_code == 422
    assert wildcard.status_code == 422
    assert path.status_code == 422

    activate_key(client, organisation_id=org, workspace_id=workspace, credential_id=widget["public_credential_id"], email="admin@example.test")
    publish_widget(client, organisation_id=org, workspace_id=workspace, widget=widget, email="admin@example.test")
    final_remove = client.delete(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/origins/{first.json()['data']['id']}",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
    )
    assert final_remove.status_code == 422

    second = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="http://127.0.0.1:3001")
    assert second.status_code == 201
    removed = client.delete(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/origins/{first.json()['data']['id']}",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
    )
    assert removed.status_code == 200
    assert removed.json()["data"]["active"] is False

    prod = create_widget(client, organisation_id=org, workspace_id=workspace, email="admin@example.test", environment="production")
    prod_localhost = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=prod["id"], email="admin@example.test", origin="http://localhost:3000")
    prod_https = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=prod["id"], email="admin@example.test", origin="https://Example.COM:443/")
    prod_duplicate = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=prod["id"], email="admin@example.test", origin="https://example.com")
    assert prod_localhost.status_code == 422
    assert prod_https.status_code == 201
    assert prod_https.json()["data"]["origin"] == "https://example.com"
    assert prod_duplicate.status_code == 422


def test_public_key_rotation_cutover_embed_and_cache_isolation(client: TestClient) -> None:
    org, workspace = seed_tenant(client, slug="alpha", email="admin@example.test")
    widget = create_widget(client, organisation_id=org, workspace_id=workspace, email="admin@example.test")
    origin = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="admin@example.test", origin="http://localhost:3000")
    assert origin.status_code == 201
    activate_key(client, organisation_id=org, workspace_id=workspace, credential_id=widget["public_credential_id"], email="admin@example.test")
    publish_widget(client, organisation_id=org, workspace_id=workspace, widget=widget, email="admin@example.test")

    old_key = widget["public_identifier"]
    first_config = public_config(client, old_key)
    assert first_config.status_code == 200
    old_etag = first_config.headers["etag"]

    rotation = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/rotate-key",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"expected_public_credential_id": widget["public_credential_id"]},
    )
    assert rotation.status_code == 200
    rotated = rotation.json()["data"]
    new_key = rotated["public_key"]
    assert new_key != old_key
    assert rotated["old_key_revoked"] is True
    assert rotated["embed_update_required"] is True

    assert public_config(client, old_key).status_code == 404
    new_config_with_old_etag = public_config(client, new_key, etag=old_etag)
    assert new_config_with_old_etag.status_code == 200
    assert new_config_with_old_etag.json()["widget"]["bot_name"] == "Admissions Assistant"
    assert new_config_with_old_etag.headers["etag"] != old_etag

    stale_rotation = client.post(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/rotate-key",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"expected_public_credential_id": widget["public_credential_id"]},
    )
    assert stale_rotation.status_code == 409

    embed = client.get(f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/embed", params={"organisation_id": org}, headers=headers("admin@example.test"))
    assert embed.status_code == 200
    data = embed.json()["data"]
    assert data["public_key"] == new_key
    assert new_key in data["snippet"]
    assert "latest" not in data["snippet"]
    assert "session" not in data["snippet"].lower()
    assert data["version_mode"] == "managed_major"
    assert data["sri"] is None
    assert data["selected_loader_path"] == "/widget-sdk/v1/loader.js"

    pinned = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/embed",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"version_mode": "pinned", "pinned_sdk_version": "0.1.0-foundation.0"},
    )
    assert pinned.status_code == 200
    pinned_data = pinned.json()["data"]
    assert pinned_data["selected_loader_path"] == "/widget-sdk/v0.1.0-foundation.0/loader.js"
    assert "integrity=" in pinned_data["snippet"] or pinned_data["sri"] is None

    unsupported = client.patch(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/embed",
        params={"organisation_id": org},
        headers=headers("admin@example.test"),
        json={"version_mode": "pinned", "pinned_sdk_version": "https://evil.test/loader.js"},
    )
    assert unsupported.status_code == 422

    versions = client.get(f"/api/v1/workspaces/{workspace}/widget-sdk-versions", params={"organisation_id": org}, headers=headers("admin@example.test"))
    assert versions.status_code == 200
    assert versions.json()["data"]["recommended"] == "0.1.0-foundation.0"
    assert all("latest" not in item["immutable_loader_path"] for item in versions.json()["data"]["versions"])

    with client.app.state.testing_session() as db:
        old = db.execute(select(PublicCredential).where(PublicCredential.public_identifier == old_key)).scalar_one()
        assert old.status == "revoked"
        actions = {event.action for event in db.execute(select(AuditEvent)).scalars().all()}
        assert {"widget_origin_added", "widget_public_key_rotated", "widget_embed_version_changed"}.issubset(actions)
        assert old_key not in str([event.metadata_json for event in db.execute(select(AuditEvent)).scalars().all()])


def test_widget_b2_admin_tenant_scope_and_rbac(client: TestClient) -> None:
    org_a, workspace_a = seed_tenant(client, slug="alpha", email="alpha@example.test")
    org_b, workspace_b = seed_tenant(client, slug="beta", email="beta@example.test")
    viewer_org, viewer_workspace = seed_tenant(client, slug="viewer", email="viewer@example.test", role="viewer")
    widget = create_widget(client, organisation_id=org_a, workspace_id=workspace_a, email="alpha@example.test")

    viewer_widget = client.post(
        f"/api/v1/workspaces/{viewer_workspace}/widgets/{widget['id']}/origins",
        params={"organisation_id": viewer_org},
        headers=headers("viewer@example.test", "viewer"),
        json={"origin": "http://localhost:3000"},
    )
    cross_origin = client.post(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget['id']}/origins",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test"),
        json={"origin": "http://localhost:3000"},
    )
    cross_embed = client.get(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget['id']}/embed",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test"),
    )
    cross_rotate = client.post(
        f"/api/v1/workspaces/{workspace_b}/widgets/{widget['id']}/rotate-key",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test"),
        json={"expected_public_credential_id": widget["public_credential_id"]},
    )

    assert viewer_widget.status_code == 403
    assert cross_origin.status_code == 404
    assert cross_embed.status_code == 404
    assert cross_rotate.status_code == 404

def test_widget_b4_installation_status_records_only_valid_allowed_origin(client: TestClient) -> None:
    org, workspace = seed_tenant(client, slug="install", email="install@example.test")
    widget = create_widget(client, organisation_id=org, workspace_id=workspace, email="install@example.test")
    added = add_origin(client, organisation_id=org, workspace_id=workspace, widget_id=widget["id"], email="install@example.test", origin="http://localhost:3000")
    assert added.status_code == 201
    activate_key(client, organisation_id=org, workspace_id=workspace, credential_id=widget["public_credential_id"], email="install@example.test")
    publish_widget(client, organisation_id=org, workspace_id=workspace, widget=widget, email="install@example.test")

    before = client.get(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": org},
        headers=headers("install@example.test"),
    )
    assert before.status_code == 200
    assert before.json()["data"] == [{"origin": "http://localhost:3000", "status": "not_observed", "last_seen_at": None, "sdk_version": None, "protocol_major": None}]

    denied = public_config(client, widget["public_identifier"], origin="http://unauthorised.localhost:3001")
    assert denied.status_code in {403, 404}
    observed = public_config(client, widget["public_identifier"])
    assert observed.status_code == 200

    after = client.get(
        f"/api/v1/workspaces/{workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": org},
        headers=headers("install@example.test"),
    )
    assert after.status_code == 200
    item = after.json()["data"][0]
    assert item["origin"] == "http://localhost:3000"
    assert item["status"] == "observed"
    assert item["last_seen_at"] is not None
    assert item["sdk_version"] is None

    cross_org, cross_workspace = seed_tenant(client, slug="install-beta", email="install-beta@example.test")
    cross = client.get(
        f"/api/v1/workspaces/{cross_workspace}/widgets/{widget['id']}/installation-status",
        params={"organisation_id": cross_org},
        headers=headers("install-beta@example.test"),
    )
    assert cross.status_code == 404

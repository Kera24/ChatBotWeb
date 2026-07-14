from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.credentials.repository import resolve_credential_by_public_identifier
from app.access.credentials.registry import DatabaseCredentialRegistry
from app.access.credentials.service import (
    CredentialValidationError,
    add_origin,
    create_credential,
    generate_public_identifier,
    normalise_origin,
    rotate_credential,
    transition_credential,
)
from app.access.errors import PublicAccessError
from app.access.widget_config.service import publish_configuration, safe_public_configuration, upsert_draft_configuration
from app.access.widget_config.validation import WidgetValidationError
from app.db.base import Base
from app.db.models import AuditEvent, CredentialAllowedOrigin, Membership, Organisation, PublicCredential, User, WidgetConfiguration, Workspace
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


def seed_tenant(client: TestClient, *, slug: str, email: str, role: str = "client_admin", org_status: str = "active", workspace_status: str = "active") -> tuple[str, str, str]:
    with client.app.state.testing_session() as db:
        org = Organisation(name=f"{slug} Org", slug=slug, status=org_status)
        user = User(email=email)
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"{slug}-knowledge", status=workspace_status)
        membership = Membership(organisation=org, user=user, role=role)
        db.add_all([org, user, workspace, membership])
        db.commit()
        return org.id, workspace.id, user.id


def create_api_credential(client: TestClient, *, organisation_id: str, workspace_id: str, email: str, role: str = "client_admin", **payload):
    body = {
        "credential_type": "widget_public_key",
        "display_name": "Website widget",
        "environment": "development",
        "policy_profile": "widget",
        "capabilities": ["widget_config"],
    }
    body.update(payload)
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/public-credentials",
        params={"organisation_id": organisation_id},
        headers=headers(email, role),
        json=body,
    )


def test_identifier_format_uniqueness_and_no_tenant_information() -> None:
    first = generate_public_identifier(credential_type="widget_public_key", environment="production")
    second = generate_public_identifier(credential_type="widget_public_key", environment="production")

    assert first.startswith("wpk_live_")
    assert second.startswith("wpk_live_")
    assert first != second
    assert "org" not in first.lower()
    assert "workspace" not in first.lower()


def test_tenant_safe_credential_create_list_get_and_public_resolution(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(
            db,
            organisation_id=org,
            workspace_id=workspace,
            credential_type="widget_public_key",
            display_name="Website widget",
            environment="development",
            policy_profile="widget",
            capabilities=["widget_config"],
            created_by_user_id=user_id,
        )
        fetched = resolve_credential_by_public_identifier(db, public_identifier=credential.public_identifier)
        assert fetched is not None
        assert fetched.organisation_id == org
        assert fetched.workspace_id == workspace
        assert fetched.secret_hash is None
        assert len(db.execute(select(PublicCredential)).scalars().all()) == 1


def test_cross_tenant_admin_access_not_found(client: TestClient) -> None:
    org_a, workspace_a, _ = seed_tenant(client, slug="alpha", email="alpha@example.test")
    org_b, workspace_b, _ = seed_tenant(client, slug="beta", email="beta@example.test")
    created = create_api_credential(client, organisation_id=org_a, workspace_id=workspace_a, email="alpha@example.test")
    credential_id = created.json()["data"]["id"]

    response = client.get(
        f"/api/v1/workspaces/{workspace_b}/public-credentials/{credential_id}",
        params={"organisation_id": org_b},
        headers=headers("beta@example.test", "client_admin"),
    )

    assert response.status_code == 404


def test_active_disabled_revoked_expired_database_resolution(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="active", actor_user_id=user_id)
        assert DatabaseCredentialRegistry(db).resolve(credential.public_identifier).credential_id == credential.id
        transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="disabled", actor_user_id=user_id)
        with pytest.raises(PublicAccessError) as disabled:
            DatabaseCredentialRegistry(db).resolve(credential.public_identifier)
        assert disabled.value.code == "disabled_credential"
        transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="revoked", actor_user_id=user_id)
        with pytest.raises(PublicAccessError) as revoked:
            DatabaseCredentialRegistry(db).resolve(credential.public_identifier)
        assert revoked.value.code == "invalid_credential"


def test_lifecycle_transitions_and_revoked_terminal(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        active = transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="active", actor_user_id=user_id)
        assert active.status == "active"
        disabled = transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="disabled", actor_user_id=user_id)
        assert disabled.status == "disabled"
        active_again = transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="active", actor_user_id=user_id)
        assert active_again.status == "active"
        revoked = transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="revoked", actor_user_id=user_id)
        assert revoked.status == "revoked"
        with pytest.raises(CredentialValidationError):
            transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="active", actor_user_id=user_id)


def test_origin_normalisation_duplicate_localhost_and_wildcard_rules(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    assert normalise_origin("https://*.Example.com", environment="production") == {
        "scheme": "https",
        "hostname": "example.com",
        "port": None,
        "wildcard_subdomains": True,
        "environment": "production",
    }
    with pytest.raises(Exception):
        normalise_origin("https://example.com/path", environment="production")
    with pytest.raises(Exception):
        normalise_origin("http://localhost:3000", environment="production")
    assert normalise_origin("http://localhost:3000", environment="development")["hostname"] == "localhost"
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        first = add_origin(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, origin="http://localhost:3000", wildcard_subdomains=False, actor_user_id=user_id)
        assert first.hostname == "localhost"
        with pytest.raises(Exception):
            add_origin(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, origin="http://localhost:3000", wildcard_subdomains=False, actor_user_id=user_id)


def test_widget_configuration_validation_publish_and_safe_public_config(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        configuration = upsert_draft_configuration(
            db,
            organisation_id=org,
            workspace_id=workspace,
            credential_id=credential.id,
            actor_user_id=user_id,
            payload={
                "bot_name": "Admissions Assistant",
                "welcome_message": "Ask about admissions.",
                "launcher_label": "Ask us",
                "primary_colour": "#111827",
                "suggested_questions_json": ["How do I apply?"],
                "max_initial_suggestions": 1,
            },
        )
        assert configuration.status == "draft"
        published = publish_configuration(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, actor_user_id=user_id)
        assert published.status == "published"
        assert published.configuration_version == 1
        safe = safe_public_configuration(published)
        assert safe["bot_name"] == "Admissions Assistant"
        assert "organisation_id" not in safe
        assert "credential_id" not in safe
        assert "policy_profile" not in safe
        with pytest.raises(WidgetValidationError):
            upsert_draft_configuration(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, actor_user_id=user_id, payload={"welcome_message": "<script>alert(1)</script>"})


def test_one_configuration_per_credential(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        upsert_draft_configuration(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, actor_user_id=user_id, payload={"bot_name": "One"})
        upsert_draft_configuration(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, actor_user_id=user_id, payload={"bot_name": "Two"})
        assert len(db.execute(select(WidgetConfiguration)).scalars().all()) == 1


def test_rotation_replacement_overlap_and_audit(client: TestClient) -> None:
    org, workspace, user_id = seed_tenant(client, slug="alpha", email="admin@example.test")
    with client.app.state.testing_session() as db:
        credential = create_credential(db, organisation_id=org, workspace_id=workspace, credential_type="widget_public_key", display_name="Widget", environment="development", policy_profile="widget", capabilities=["widget_config"], created_by_user_id=user_id)
        transition_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, target_status="active", actor_user_id=user_id)
        replacement = rotate_credential(db, organisation_id=org, workspace_id=workspace, credential_id=credential.id, actor_user_id=user_id)
        assert replacement.parent_credential_id == credential.id
        assert replacement.rotation_group_id == credential.rotation_group_id
        assert replacement.status == "draft"
        assert replacement.public_identifier != credential.public_identifier
        events = db.execute(select(AuditEvent).where(AuditEvent.action == "public_credential.rotated")).scalars().all()
        assert len(events) == 1


def test_no_automatic_public_exposure_or_widget_config(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="admin@example.test")
    response = create_api_credential(client, organisation_id=org, workspace_id=workspace, email="admin@example.test")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "draft"
    assert data["widget_configuration_status"] is None
    with client.app.state.testing_session() as db:
        assert db.execute(select(CredentialAllowedOrigin)).scalars().all() == []


def test_admin_api_rbac_create_list_read_update_and_safe_response(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="owner@example.test", role="org_owner")
    viewer_org, viewer_workspace, _ = seed_tenant(client, slug="viewer", email="viewer@example.test", role="viewer")
    contributor_org, contributor_workspace, _ = seed_tenant(client, slug="contrib", email="contrib@example.test", role="contributor")

    created = create_api_credential(client, organisation_id=org, workspace_id=workspace, email="owner@example.test", role="org_owner")
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["public_identifier"].startswith("wpk_dev_")
    assert "secret_hash" not in created.text
    credential_id = data["id"]

    listed = client.get(f"/api/v1/workspaces/{workspace}/public-credentials", params={"organisation_id": org}, headers=headers("owner@example.test", "org_owner"))
    read = client.get(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}", params={"organisation_id": org}, headers=headers("owner@example.test", "org_owner"))
    patched = client.patch(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}", params={"organisation_id": org}, headers=headers("owner@example.test", "org_owner"), json={"display_name": "Updated widget"})
    viewer_denied = create_api_credential(client, organisation_id=viewer_org, workspace_id=viewer_workspace, email="viewer@example.test", role="viewer")
    contributor_denied = create_api_credential(client, organisation_id=contributor_org, workspace_id=contributor_workspace, email="contrib@example.test", role="contributor")
    non_member = client.get(f"/api/v1/workspaces/{workspace}/public-credentials", params={"organisation_id": org}, headers=headers("viewer@example.test", "viewer"))

    assert listed.status_code == 200 and listed.json()["data"][0]["id"] == credential_id
    assert read.status_code == 200 and read.json()["data"]["id"] == credential_id
    assert patched.status_code == 200 and patched.json()["data"]["display_name"] == "Updated widget"
    assert viewer_denied.status_code == 403
    assert contributor_denied.status_code == 403
    assert non_member.status_code == 403


def test_admin_api_lifecycle_rotation_origins_widget_config_and_audit(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="admin@example.test")
    created = create_api_credential(client, organisation_id=org, workspace_id=workspace, email="admin@example.test")
    credential_id = created.json()["data"]["id"]

    active = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/activate", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    disabled = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/disable", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    rotated = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/rotate", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    origin_added = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/origins", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"), json={"origin": "http://localhost:3000"})
    origins = client.get(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/origins", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    origin_id = origin_added.json()["data"]["id"]
    origin_removed = client.delete(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/origins/{origin_id}", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    config = client.put(
        f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/widget-config",
        params={"organisation_id": org},
        headers=headers("admin@example.test", "client_admin"),
        json={"bot_name": "Admissions Assistant", "suggested_questions_json": ["How do I apply?"], "max_initial_suggestions": 1},
    )
    published = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/widget-config/publish", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    revoked = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/revoke", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))
    invalid = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/activate", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"))

    assert active.status_code == 200 and active.json()["data"]["status"] == "active"
    assert disabled.status_code == 200 and disabled.json()["data"]["status"] == "disabled"
    assert rotated.status_code == 201 and rotated.json()["data"]["parent_credential_id"] == credential_id
    assert origin_added.status_code == 201
    assert origins.status_code == 200 and len(origins.json()["data"]) == 1
    assert origin_removed.status_code == 200 and origin_removed.json()["data"]["active"] is False
    assert config.status_code == 200 and config.json()["data"]["bot_name"] == "Admissions Assistant"
    assert published.status_code == 200 and published.json()["data"]["configuration_version"] == 1
    assert "organisation_id" not in str(published.json()["data"]["safe_public_configuration"])
    assert revoked.status_code == 200 and revoked.json()["data"]["status"] == "revoked"
    assert invalid.status_code == 422
    with client.app.state.testing_session() as db:
        actions = {event.action for event in db.execute(select(AuditEvent)).scalars().all()}
        assert "public_credential.created" in actions
        assert "public_credential.activated" in actions
        assert "public_credential.disabled" in actions
        assert "public_credential.rotated" in actions
        assert "public_credential.revoked" in actions
        assert "public_credential.origin.added" in actions
        assert "public_credential.origin.removed" in actions
        assert "widget_configuration.created" in actions
        assert "widget_configuration.published" in actions


def test_invalid_widget_configuration_and_origin_api_errors(client: TestClient) -> None:
    org, workspace, _ = seed_tenant(client, slug="alpha", email="admin@example.test")
    created = create_api_credential(client, organisation_id=org, workspace_id=workspace, email="admin@example.test", environment="production")
    credential_id = created.json()["data"]["id"]

    invalid_origin = client.post(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/origins", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"), json={"origin": "http://localhost:3000"})
    invalid_config = client.put(f"/api/v1/workspaces/{workspace}/public-credentials/{credential_id}/widget-config", params={"organisation_id": org}, headers=headers("admin@example.test", "client_admin"), json={"welcome_message": "<b>unsafe</b>"})

    assert invalid_origin.status_code == 422
    assert invalid_config.status_code == 422


def test_alembic_upgrade_creates_public_access_tables(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    from app.core.config import settings

    db_path = tmp_path / "migration-smoke.db"
    previous_url = settings.DATABASE_URL
    object.__setattr__(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        tables = set(inspect(engine).get_table_names())
    finally:
        object.__setattr__(settings, "DATABASE_URL", previous_url)

    assert {"public_credentials", "credential_allowed_origins", "widget_configurations"}.issubset(tables)

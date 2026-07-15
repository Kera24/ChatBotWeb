from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.credentials.service import add_origin, create_credential, transition_credential
from app.access.observability.events import InMemoryAccessEventSink
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.access.rate_limit.token_bucket import TokenBucketState
from app.access.widget_config.service import publish_configuration, upsert_draft_configuration
from app.db.base import Base
from app.db.models import ChatSession, Organisation, PublicSession, User, WidgetConfiguration, Workspace
from app.db.session import get_db
from app.main import create_app


class DenyRateLimitStore:
    def consume(self, **_kwargs):
        return TokenBucketState(allowed=False, remaining=0, retry_after_seconds=17, reset_after_seconds=17, ttl_seconds=60)

    def health_check(self) -> bool:
        return True


class UnavailableRateLimitStore:
    def consume(self, **_kwargs):
        from app.access.rate_limit.errors import RateLimitStoreError

        raise RateLimitStoreError("redis unavailable")

    def health_check(self) -> bool:
        return False


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession
    app.state.public_widget_rate_limit_store = InMemoryRateLimitStore()
    app.state.public_widget_event_sink = InMemoryAccessEventSink()

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def seed_widget(client: TestClient, *, environment: str = "development", origin: str = "http://localhost:3000", wildcard: bool = False, config_status: str = "published", credential_type: str = "widget_public_key", credential_status: str = "active", org_status: str = "active", workspace_status: str = "active") -> str:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name="Alpha Org", slug=f"alpha-{environment}-{credential_type}-{credential_status}-{unique}", status="active")
        user = User(email=f"admin-{environment}-{credential_status}-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"knowledge-{environment}-{credential_status}-{unique}", status="active")
        db.add_all([org, user, workspace])
        db.commit()
        credential = create_credential(
            db,
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_type=credential_type,
            display_name="Website widget",
            environment=environment,
            policy_profile="widget",
            capabilities=["widget_config"],
            created_by_user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        if credential_status == "active":
            credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="active", actor_user_id=user.id)
        elif credential_status == "disabled":
            credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="active", actor_user_id=user.id)
            credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="disabled", actor_user_id=user.id)
        elif credential_status == "revoked":
            credential = transition_credential(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, target_status="revoked", actor_user_id=user.id)
        add_origin(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, origin=origin, wildcard_subdomains=wildcard, actor_user_id=user.id)
        if config_status != "missing":
            upsert_draft_configuration(
                db,
                organisation_id=org.id,
                workspace_id=workspace.id,
                credential_id=credential.id,
                actor_user_id=user.id,
                payload={"bot_name": "Admissions", "show_citations": False, "allow_conversation_history": True},
            )
            if config_status == "published":
                publish_configuration(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, actor_user_id=user.id)
            elif config_status == "disabled":
                config = db.execute(select(WidgetConfiguration).where(WidgetConfiguration.credential_id == credential.id)).scalar_one()
                config.status = "disabled"
                db.commit()
        if org_status != "active" or workspace_status != "active":
            org.status = org_status
            workspace.status = workspace_status
            db.commit()
        return credential.public_identifier


def post_session(client: TestClient, public_key: str, *, origin: str | None = "http://localhost:3000", body: dict | None = None, headers: dict[str, str] | None = None):
    request_headers = {"Content-Type": "application/json", "X-Request-ID": "req-widget-1"}
    if origin is not None:
        request_headers["Origin"] = origin
    if headers:
        request_headers.update(headers)
    return client.post(f"/api/v1/widget/{public_key}/sessions", headers=request_headers, json={} if body is None else body)


def test_public_widget_session_creation_returns_safe_token_and_persists_session(client: TestClient) -> None:
    public_key = seed_widget(client)

    response = post_session(client, public_key)

    assert response.status_code == 201
    body = response.json()
    assert body["session_token"].startswith("pss_dev_")
    assert body["remaining_messages"] == body["max_messages"]
    assert body["configuration_version"] == 1
    assert body["capabilities"] == {"can_send_messages": True, "conversation_history_enabled": True, "citations_enabled": False}
    for excluded in ("organisation_id", "workspace_id", "credential_id", "conversation_id", "token_hash", "policy_profile", "allowed_origins"):
        assert excluded not in body
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "false"
    assert response.headers["vary"] == "Origin"
    with client.app.state.testing_session() as db:
        sessions = db.execute(select(PublicSession)).scalars().all()
        assert len(sessions) == 1
        assert sessions[0].channel == "widget"
        assert sessions[0].conversation_id is None
        assert sessions[0].token_secret_hash not in body["session_token"]
        assert db.execute(select(ChatSession)).scalars().all() == []
    events = [event.to_dict() for event in client.app.state.public_widget_event_sink.events]
    assert "widget.session.created" in [event["event_type"] for event in events]
    assert public_key not in str(events)
    assert "http://localhost:3000" not in str(events)
    assert body["session_token"] not in str(events)


def test_empty_body_allowed_and_forbidden_public_fields_rejected(client: TestClient) -> None:
    public_key = seed_widget(client)

    assert post_session(client, public_key, body={}).status_code == 201
    rejected = post_session(client, public_key, body={"organisation_id": "org-1", "message": "hello", "email": "user@example.test"})

    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_request"


def test_invalid_widget_identity_and_unpublished_config_are_enumeration_resistant(client: TestClient) -> None:
    draft_key = seed_widget(client, config_status="draft")
    missing_config_key = seed_widget(client, config_status="missing")

    for public_key in ("wpk_dev_missing", draft_key, missing_config_key):
        response = post_session(client, public_key)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "invalid_widget"
        assert "organisation" not in str(response.json()).lower()
        assert "workspace" not in str(response.json()).lower()


def test_disabled_revoked_wrong_type_and_inactive_tenant_are_safe_invalid_widget(client: TestClient) -> None:
    disabled_key = seed_widget(client, credential_status="disabled")
    revoked_key = seed_widget(client, credential_status="revoked")
    inactive_org_key = seed_widget(client, org_status="disabled")
    inactive_workspace_key = seed_widget(client, workspace_status="disabled")

    for public_key in (disabled_key, revoked_key, inactive_org_key, inactive_workspace_key):
        response = post_session(client, public_key)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "invalid_widget"


def test_origin_required_disallowed_malformed_and_production_http_rejected(client: TestClient) -> None:
    public_key = seed_widget(client)
    prod_key = seed_widget(client, environment="production", origin="https://example.com")

    missing = post_session(client, public_key, origin=None)
    disallowed = post_session(client, public_key, origin="http://evil.test")
    malformed = post_session(client, public_key, origin="not an origin")
    insecure = post_session(client, prod_key, origin="http://example.com")

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "origin_required"
    assert disallowed.status_code == 403
    assert disallowed.json()["error"]["code"] == "origin_not_allowed"
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "malformed_origin"
    assert insecure.status_code == 403
    assert insecure.json()["error"]["code"] == "origin_not_allowed"
    assert "localhost" not in str(disallowed.json()).lower()
    with client.app.state.testing_session() as db:
        assert db.execute(select(PublicSession)).scalars().all() == []


def test_wildcard_origin_and_preflight_cors(client: TestClient) -> None:
    public_key = seed_widget(client, environment="production", origin="https://*.example.com", wildcard=True)

    preflight = client.options(
        f"/api/v1/widget/{public_key}/sessions",
        headers={"Origin": "https://help.example.com", "Access-Control-Request-Method": "POST"},
    )
    response = post_session(client, public_key, origin="https://help.example.com")

    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == "https://help.example.com"
    assert preflight.headers["access-control-allow-methods"] == "POST, OPTIONS"
    assert preflight.headers["access-control-allow-credentials"] == "false"
    assert preflight.headers["vary"] == "Origin"
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == "https://help.example.com"


def test_dashboard_headers_are_rejected_and_no_session_created(client: TestClient) -> None:
    public_key = seed_widget(client)

    response = post_session(client, public_key, headers={"X-Development-User-Email": "admin@example.test", "X-Development-Role": "super_admin"})
    bearer = post_session(client, public_key, headers={"Authorization": "Bearer dashboard-token"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert bearer.status_code == 400
    with client.app.state.testing_session() as db:
        assert db.execute(select(PublicSession)).scalars().all() == []


def test_rate_limited_and_redis_unavailable_fail_closed_before_session_creation(client: TestClient) -> None:
    public_key = seed_widget(client)
    client.app.state.public_widget_rate_limit_store = DenyRateLimitStore()

    limited = post_session(client, public_key)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["retry-after"] == "17"
    with client.app.state.testing_session() as db:
        assert db.execute(select(PublicSession)).scalars().all() == []

    client.app.state.public_widget_rate_limit_store = UnavailableRateLimitStore()
    unavailable = post_session(client, public_key)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "temporarily_unavailable"


def test_public_widget_routes_are_limited_to_approved_surface(client: TestClient) -> None:
    paths = {route.path for route in client.app.routes}

    assert "/api/v1/widget/{public_key}/sessions" in paths
    assert "/api/v1/widget/{public_key}/messages" in paths
    assert "/api/v1/widget/{public_key}/config" in paths
    assert not any(path.startswith("/api/v1/public-access") for path in paths)

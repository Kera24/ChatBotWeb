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


def seed_widget(
    client: TestClient,
    *,
    environment: str = "development",
    origin: str = "http://localhost:3000",
    wildcard: bool = False,
    config_status: str = "published",
    credential_status: str = "active",
    org_status: str = "active",
    workspace_status: str = "active",
    logo_path: str | None = None,
    avatar_path: str | None = None,
) -> str:
    with client.app.state.testing_session() as db:
        unique = uuid4().hex[:8]
        org = Organisation(name="Alpha Org", slug=f"config-alpha-{unique}", status="active")
        user = User(email=f"config-admin-{unique}@example.test")
        workspace = Workspace(organisation=org, name="Knowledge", slug=f"config-knowledge-{unique}", status="active")
        db.add_all([org, user, workspace])
        db.commit()
        credential = create_credential(
            db,
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_type="widget_public_key",
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
                payload={
                    "bot_name": "Admissions",
                    "welcome_message": "Ask us about courses.",
                    "launcher_label": "Chat now",
                    "primary_colour": "#0f766e",
                    "secondary_colour": "#111827",
                    "show_citations": False,
                    "allow_conversation_history": True,
                    "suggested_questions_json": ["How do I apply?", "What are the fees?", "Can I study online?"],
                    "max_initial_suggestions": 2,
                    "privacy_notice_text": "We use chat data to improve support.",
                    "privacy_notice_url": "https://example.com/privacy",
                    "terms_url": "https://example.com/terms",
                    "fallback_contact_text": "Contact admissions if chat is unavailable.",
                    "logo_path": logo_path,
                    "avatar_path": avatar_path,
                },
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


def get_config(client: TestClient, public_key: str, *, origin: str | None = "http://localhost:3000", headers: dict[str, str] | None = None, query: str = ""):
    request_headers = {"X-Request-ID": "req-config-1"}
    if origin is not None:
        request_headers["Origin"] = origin
    if headers:
        request_headers.update(headers)
    return client.get(f"/api/v1/widget/{public_key}/config{query}", headers=request_headers)


def test_public_widget_config_returns_safe_published_projection_without_side_effects(client: TestClient) -> None:
    public_key = seed_widget(client, logo_path="https://cdn.example.test/logo.png", avatar_path="avatars/bot.webp")

    response = get_config(client, public_key)

    assert response.status_code == 200
    body = response.json()
    assert body["widget"]["bot_name"] == "Admissions"
    assert body["widget"]["logo_url"] == "https://cdn.example.test/logo.png"
    assert body["widget"]["avatar_url"] is None
    assert body["behaviour"]["suggested_questions"] == ["How do I apply?", "What are the fees?", "Can I study online?"]
    assert body["behaviour"]["max_initial_suggestions"] == 2
    assert body["capabilities"] == {"can_create_session": True, "can_send_messages": True, "citations_enabled": False, "conversation_history_enabled": True}
    assert body["configuration_version"] == 1
    assert body["response_schema_version"] == "1.0"
    assert body["request_id"] == "req-config-1"
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "false"
    assert response.headers["vary"] == "Origin"
    assert response.headers["etag"].startswith('"')
    assert response.headers["cache-control"].startswith("public, max-age=60")
    for excluded in ("organisation_id", "workspace_id", "credential_id", "allowed_origins", "policy_profile", "metadata_json", "provider_key", "model_key"):
        assert excluded not in str(body)
    with client.app.state.testing_session() as db:
        assert db.execute(select(PublicSession)).scalars().all() == []
        assert db.execute(select(ChatSession)).scalars().all() == []
    events = [event.to_dict() for event in client.app.state.public_widget_event_sink.events]
    assert "widget.config.served" in [event["event_type"] for event in events]
    assert "widget.config.asset_omitted" in [event["event_type"] for event in events]
    assert public_key not in str(events)
    assert "http://localhost:3000" not in str(events)


def test_public_widget_config_eligibility_errors_are_enumeration_resistant(client: TestClient) -> None:
    draft_key = seed_widget(client, config_status="draft")
    missing_config_key = seed_widget(client, config_status="missing")
    disabled_key = seed_widget(client, credential_status="disabled")
    revoked_key = seed_widget(client, credential_status="revoked")
    inactive_org_key = seed_widget(client, org_status="disabled")
    inactive_workspace_key = seed_widget(client, workspace_status="disabled")

    for public_key in ("wpk_dev_missing", draft_key, missing_config_key, disabled_key, revoked_key, inactive_org_key, inactive_workspace_key):
        response = get_config(client, public_key)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "invalid_widget"
        assert "organisation" not in str(response.json()).lower()
        assert "workspace" not in str(response.json()).lower()
        assert response.headers["cache-control"] == "no-store"


def test_public_widget_config_origin_and_cors_policy(client: TestClient) -> None:
    public_key = seed_widget(client)
    prod_key = seed_widget(client, environment="production", origin="https://example.com")
    wildcard_key = seed_widget(client, environment="production", origin="https://*.example.com", wildcard=True)

    assert get_config(client, public_key, origin=None).json()["error"]["code"] == "origin_required"
    disallowed = get_config(client, public_key, origin="http://evil.test")
    malformed = get_config(client, public_key, origin="not an origin")
    insecure = get_config(client, prod_key, origin="http://example.com")
    wildcard = get_config(client, wildcard_key, origin="https://help.example.com")

    assert disallowed.status_code == 403
    assert disallowed.json()["error"]["code"] == "origin_not_allowed"
    assert "access-control-allow-origin" not in disallowed.headers
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "malformed_origin"
    assert insecure.status_code == 403
    assert insecure.json()["error"]["code"] == "origin_not_allowed"
    assert wildcard.status_code == 200
    assert wildcard.headers["access-control-allow-origin"] == "https://help.example.com"

    preflight = client.options(
        f"/api/v1/widget/{wildcard_key}/config",
        headers={"Origin": "https://help.example.com", "Access-Control-Request-Method": "GET"},
    )
    denied_preflight = client.options(
        f"/api/v1/widget/{wildcard_key}/config",
        headers={"Origin": "https://evil.test", "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == "https://help.example.com"
    assert preflight.headers["access-control-allow-methods"] == "GET, OPTIONS"
    assert preflight.headers["access-control-allow-credentials"] == "false"
    assert preflight.headers["vary"] == "Origin"
    assert denied_preflight.status_code == 403
    assert "access-control-allow-origin" not in denied_preflight.headers


def test_public_widget_config_rate_limit_denial_and_unavailable(client: TestClient) -> None:
    public_key = seed_widget(client)
    client.app.state.public_widget_rate_limit_store = DenyRateLimitStore()

    limited = get_config(client, public_key)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.headers["retry-after"] == "17"
    assert "widget" not in limited.json()

    client.app.state.public_widget_rate_limit_store = UnavailableRateLimitStore()
    unavailable = get_config(client, public_key)
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "temporarily_unavailable"


def test_public_widget_config_etag_conditional_get(client: TestClient) -> None:
    public_key = seed_widget(client)

    first = get_config(client, public_key)
    second = get_config(client, public_key, headers={"If-None-Match": first.headers["etag"]})

    assert first.status_code == 200
    assert second.status_code == 304
    assert second.text == ""
    assert second.headers["etag"] == first.headers["etag"]
    assert second.headers["vary"] == "Origin"
    assert second.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert second.headers["cache-control"].startswith("public, max-age=60")
    events = [event.event_type for event in client.app.state.public_widget_event_sink.events]
    assert "widget.config.not_modified" in events


def test_public_widget_config_rejects_dashboard_headers_queries_and_bodies(client: TestClient) -> None:
    public_key = seed_widget(client)

    dev_header = get_config(client, public_key, headers={"X-Development-User-Email": "admin@example.test"})
    bearer = get_config(client, public_key, headers={"Authorization": "Bearer dashboard-token"})
    query = get_config(client, public_key, query="?organisation_id=tenant")
    body = client.request("GET", f"/api/v1/widget/{public_key}/config", headers={"Origin": "http://localhost:3000", "Content-Length": "2"}, content="{}")

    for response in (dev_header, bearer, query, body):
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_request"
    with client.app.state.testing_session() as db:
        assert db.execute(select(PublicSession)).scalars().all() == []


def test_public_widget_config_asset_safety(client: TestClient) -> None:
    public_key = seed_widget(client)
    with client.app.state.testing_session() as db:
        config = db.execute(select(WidgetConfiguration)).scalar_one()
        config.logo_path = "file:///tmp/logo.png"
        config.avatar_path = "https://cdn.example.test/avatar.svg"
        db.commit()

    response = get_config(client, public_key)

    assert response.status_code == 200
    assert response.json()["widget"]["logo_url"] is None
    assert response.json()["widget"]["avatar_url"] is None


from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.channels.base import DevelopmentTestChannelAdapter
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import InMemoryCredentialRegistry
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import InMemoryAccessEventSink
from app.access.origin_validation.contracts import AllowedOriginRecord
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.models import planned_widget_policy
from app.access.policies.registry import AccessPolicyRegistry
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.access.rate_limit.service import RateLimitService
from app.access.sessions.contracts import CreatePublicSessionCommand, ValidatePublicSessionCommand
from app.access.sessions.repository import get_by_token_id_for_verification
from app.access.sessions.service import PublicSessionChecks, PublicSessionService
from app.access.sessions.tokens import (
    generate_public_session_token,
    hash_public_session_secret,
    parse_public_session_token,
    verify_public_session_secret,
)
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks
from app.db.base import Base
from app.db.models import ChatSession, Organisation, PublicCredential, PublicSession, Workspace

NOW = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
TOKEN_SECRET = "unit-public-session-secret"
RATE_SECRET = "unit-rate-secret"


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)


def seed_public_credential(db: Session, *, org_status: str = "active", workspace_status: str = "active", credential_status: str = "active", environment: str = "development") -> PublicCredential:
    org = Organisation(name="Alpha Org", slug=f"alpha-{org_status}", status=org_status)
    workspace = Workspace(organisation=org, name="Knowledge", slug="knowledge", status=workspace_status)
    credential = PublicCredential(
        organisation_id="pending",
        workspace_id="pending",
        credential_type="widget_public_key",
        public_identifier=f"wpk_dev_{uuid4().hex}",
        display_name="Widget",
        status=credential_status,
        environment=environment,
        policy_profile="widget",
        capabilities_json=["message"],
    )
    db.add_all([org, workspace])
    db.flush()
    credential.organisation_id = org.id
    credential.workspace_id = workspace.id
    db.add(credential)
    db.flush()
    return credential


def credential_record(credential: PublicCredential) -> CredentialRecord:
    return CredentialRecord(
        credential_id=credential.id,
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        credential_type=credential.credential_type,
        public_identifier=credential.public_identifier,
        status=credential.status,
        environment=credential.environment,
        policy_profile=credential.policy_profile,
        capabilities=("message",),
    )


def session_service(db: Session, credential: PublicCredential, *, now: datetime = NOW, event_sink: InMemoryAccessEventSink | None = None) -> PublicSessionService:
    def lookup(credential_id: str) -> CredentialRecord | None:
        row = db.get(PublicCredential, credential_id)
        return credential_record(row) if row is not None else None

    return PublicSessionService(
        db=db,
        checks=PublicSessionChecks(
            organisation_is_active=lambda organisation_id: db.get(Organisation, organisation_id).status == "active",
            workspace_is_active=lambda workspace_id: db.get(Workspace, workspace_id).status == "active",
            credential_lookup=lookup,
            policy_requires_origin=lambda policy_profile: policy_profile == "widget",
        ),
        event_sink=event_sink or InMemoryAccessEventSink(),
        clock=lambda: now,
        token_hash_secret=TOKEN_SECRET,
    )


def create_command(credential: PublicCredential, **overrides) -> CreatePublicSessionCommand:
    values = {
        "organisation_id": credential.organisation_id,
        "workspace_id": credential.workspace_id,
        "credential_id": credential.id,
        "channel": "internal_test",
        "environment": credential.environment,
        "policy_profile": "widget",
        "origin_id": "origin-1",
        "canonical_origin": "http://localhost:3000",
        "inactivity_timeout_seconds": 1800,
        "absolute_lifetime_seconds": 86400,
        "max_messages": 3,
        "metadata": {"source": "unit"},
        "request_id": "req-1",
        "trace_id": "trace-1",
        "received_at": NOW,
    }
    values.update(overrides)
    return CreatePublicSessionCommand(**values)


def validate_command(credential: PublicCredential, token: str, **overrides) -> ValidatePublicSessionCommand:
    values = {
        "public_session_token": token,
        "organisation_id": credential.organisation_id,
        "workspace_id": credential.workspace_id,
        "credential_id": credential.id,
        "channel": "internal_test",
        "environment": credential.environment,
        "policy_profile": "widget",
        "canonical_origin": "http://localhost:3000",
        "received_at": NOW + timedelta(minutes=1),
        "request_id": "req-2",
        "trace_id": "trace-2",
    }
    values.update(overrides)
    return ValidatePublicSessionCommand(**values)


def test_token_format_parse_entropy_hash_and_no_tenant_information() -> None:
    first = generate_public_session_token(environment="production", token_id_bytes=16, secret_bytes=32)
    second = generate_public_session_token(environment="production", token_id_bytes=16, secret_bytes=32)

    assert first.token.startswith("pss_live_")
    assert second.token.startswith("pss_live_")
    assert first.token != second.token
    assert "org" not in first.token.lower()
    assert "workspace" not in first.token.lower()
    parsed = parse_public_session_token(first.token)
    assert parsed.environment == "production"
    assert parsed.token_id == first.token_id
    digest = hash_public_session_secret(token_id=first.token_id, secret=first.secret, hash_secret=TOKEN_SECRET, version="v1")
    assert verify_public_session_secret(token_id=first.token_id, secret=first.secret, stored_hash=digest, hash_secret=TOKEN_SECRET, version="v1") is True
    assert verify_public_session_secret(token_id=first.token_id, secret="wrong", stored_hash=digest, hash_secret=TOKEN_SECRET, version="v1") is False
    assert first.secret not in digest


@pytest.mark.parametrize("token", ["", "pss_live_missingdot", "pss_bad_abc.def", "pss_live_abc.not long enough!", "x" * 300])
def test_malformed_tokens_rejected(token: str) -> None:
    with pytest.raises(ValueError):
        parse_public_session_token(token)


def test_session_creation_persists_only_hash_and_validates(db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)

    created = service.create_session(create_command(credential))
    parts = parse_public_session_token(created.public_session_token)
    row = get_by_token_id_for_verification(db, public_token_id=parts.token_id)

    assert row is not None
    assert row.public_token_id == parts.token_id
    assert row.token_secret_hash != parts.secret
    assert created.public_session_token not in str(row.metadata_json)
    context = service.validate_session(validate_command(credential, created.public_session_token), max_messages=3, inactivity_timeout_seconds=1800)
    assert context.internal_session_id == row.id
    assert context.remaining_messages == 3
    assert context.expires_at <= context.absolute_expires_at


def test_session_creation_requires_active_tenant_credential_and_origin(db: Session) -> None:
    inactive_org_credential = seed_public_credential(db, org_status="disabled")
    with pytest.raises(Exception) as inactive_org:
        session_service(db, inactive_org_credential).create_session(create_command(inactive_org_credential))
    assert getattr(inactive_org.value, "code", None) == "invalid_session"

    active_credential = seed_public_credential(db)
    with pytest.raises(Exception) as missing_origin:
        session_service(db, active_credential).create_session(create_command(active_credential, canonical_origin=None))
    assert getattr(missing_origin.value, "code", None) == "session_origin_mismatch"


def test_validation_rejects_binding_lifecycle_origin_and_credential_changes(db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)
    token = service.create_session(create_command(credential)).public_session_token

    with pytest.raises(Exception) as cross_tenant:
        service.validate_session(validate_command(credential, token, organisation_id="other-org"), max_messages=3, inactivity_timeout_seconds=1800)
    assert getattr(cross_tenant.value, "code", None) == "invalid_session"
    with pytest.raises(Exception) as channel_mismatch:
        service.validate_session(validate_command(credential, token, channel="other"), max_messages=3, inactivity_timeout_seconds=1800)
    assert getattr(channel_mismatch.value, "code", None) == "session_channel_mismatch"
    with pytest.raises(Exception) as origin_mismatch:
        service.validate_session(validate_command(credential, token, canonical_origin="http://evil.test:80"), max_messages=3, inactivity_timeout_seconds=1800)
    assert getattr(origin_mismatch.value, "code", None) == "session_origin_mismatch"
    credential.status = "disabled"
    db.flush()
    with pytest.raises(Exception) as disabled:
        service.validate_session(validate_command(credential, token), max_messages=3, inactivity_timeout_seconds=1800)
    assert getattr(disabled.value, "code", None) == "invalid_session"


def test_expiry_extension_cap_and_terminal_states(db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)
    token = service.create_session(create_command(credential, inactivity_timeout_seconds=120, absolute_lifetime_seconds=120)).public_session_token

    context = service.validate_session(validate_command(credential, token, received_at=NOW + timedelta(seconds=90)), max_messages=3, inactivity_timeout_seconds=60)
    assert context.expires_at == NOW + timedelta(seconds=120)
    with pytest.raises(Exception) as expired:
        service.validate_session(validate_command(credential, token, received_at=NOW + timedelta(seconds=121)), max_messages=3, inactivity_timeout_seconds=60)
    assert getattr(expired.value, "code", None) == "expired_session"
    row = db.get(PublicSession, context.internal_session_id)
    assert row.status == "expired"


def test_message_slot_consumption_is_atomic_and_limited(db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)
    token = service.create_session(create_command(credential)).public_session_token
    context = service.validate_session(validate_command(credential, token), max_messages=2, inactivity_timeout_seconds=1800)

    first = service.consume_message_slot(context, max_messages=2, inactivity_timeout_seconds=1800)
    second = service.consume_message_slot(context, max_messages=2, inactivity_timeout_seconds=1800)
    assert first.remaining_messages == 1
    assert second.remaining_messages == 0
    with pytest.raises(Exception) as exhausted:
        service.consume_message_slot(context, max_messages=2, inactivity_timeout_seconds=1800)
    assert getattr(exhausted.value, "code", None) == "session_limit_reached"


def test_conversation_attachment_once_and_tenant_safe(db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)
    token = service.create_session(create_command(credential)).public_session_token
    context = service.validate_session(validate_command(credential, token), max_messages=3, inactivity_timeout_seconds=1800)
    conversation = ChatSession(organisation_id=credential.organisation_id, workspace_id=credential.workspace_id, channel="widget", status="active", started_at=NOW)
    other = ChatSession(organisation_id="other", workspace_id="other", channel="widget", status="active", started_at=NOW)
    db.add_all([conversation, other])
    db.flush()

    assert service.attach_conversation(context, conversation_id=conversation.id) == conversation.id
    assert service.attach_conversation(context, conversation_id=other.id) == conversation.id


def test_token_id_collision_retry(monkeypatch: pytest.MonkeyPatch, db: Session) -> None:
    credential = seed_public_credential(db)
    service = session_service(db, credential)
    generated = []
    real_generate = generate_public_session_token

    def fake_generate(**kwargs):
        generated.append(True)
        return real_generate(**kwargs)

    original_create = __import__("app.access.sessions.service", fromlist=["repository"]).repository.create_session

    def fake_create(db_arg, session):
        if len(generated) == 1:
            from app.access.sessions.repository import PublicSessionTokenCollisionError

            raise PublicSessionTokenCollisionError("collision")
        return original_create(db_arg, session)

    monkeypatch.setattr("app.access.sessions.service.generate_public_session_token", fake_generate)
    monkeypatch.setattr("app.access.sessions.service.repository.create_session", fake_create)

    created = service.create_session(create_command(credential))
    assert created.public_session_token.startswith("pss_dev_")
    assert len(generated) == 2


def test_alembic_upgrade_creates_public_sessions_table(tmp_path: Path) -> None:
    database_path = tmp_path / "sessions.db"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)
    assert "public_sessions" in inspector.get_table_names()
    indexes = {index["name"] for index in inspector.get_indexes("public_sessions")}
    assert "ix_public_sessions_credential_status" in indexes
    assert "ix_public_sessions_status_expires_at" in indexes


def make_gateway(db: Session, credential: PublicCredential, *, rate_limit: bool = True, origin_allowed: bool = True) -> PublicAccessGateway:
    record = credential_record(credential)
    credential_registry = InMemoryCredentialRegistry([record])
    policy = planned_widget_policy()
    policy_registry = AccessPolicyRegistry([policy])
    tenant_service = PublicTenantResolutionService(
        credential_registry=credential_registry,
        policy_registry=policy_registry,
        checks=TenantResolutionChecks(
            organisation_is_active=lambda _org: True,
            workspace_is_active=lambda _workspace: True,
            workspace_belongs_to_organisation=lambda _workspace, _org: True,
        ),
    )
    events = InMemoryAccessEventSink()
    origins = [AllowedOriginRecord("origin-1", credential.id, "http", "localhost", 3000, False, "development")] if origin_allowed else []
    origin_service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: origins, event_sink=events)
    rate_service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=RATE_SECRET, event_sink=events) if rate_limit else None
    return PublicAccessGateway(
        channel_registry=ChannelRegistry([DevelopmentTestChannelAdapter()]),
        tenant_resolution_service=tenant_service,
        policy_registry=policy_registry,
        event_sink=events,
        origin_validation_service=origin_service,
        rate_limit_service=rate_service,
        public_session_service=session_service(db, credential, event_sink=events),
    )


def raw_request(credential: PublicCredential, **overrides):
    data = {
        "request_id": "req-gateway",
        "channel": "internal_test",
        "credential_type": "widget_public_key",
        "public_identifier": credential.public_identifier,
        "message": "hello",
        "origin": "http://localhost:3000",
        "client_ip": "203.0.113.10",
        "rate_limit_category": "widget_session_create",
        "session_operation": "session_creation",
    }
    data.update(overrides)
    return data


def test_gateway_session_creation_after_origin_and_rate_limit(db: Session) -> None:
    credential = seed_public_credential(db)
    gateway = make_gateway(db, credential)

    result = gateway.validate_access(raw_request(credential))

    assert result.response.status == "session_created"
    assert result.response.payload["public_session_token"].startswith("pss_dev_")
    event_types = [event.event_type for event in gateway.event_sink.events]
    assert event_types.index("origin.validation.allowed") < event_types.index("rate_limit.allowed") < event_types.index("public_session.created")


def test_gateway_validation_requires_token_and_denials_prevent_session_stage(db: Session) -> None:
    credential = seed_public_credential(db)
    gateway = make_gateway(db, credential)

    missing = gateway.validate(raw_request(credential, session_operation="session_validation", rate_limit_category="widget_message_send"))
    assert missing.status == "rejected"
    assert missing.safe_error.code == "invalid_session"

    denied_origin = make_gateway(db, credential, origin_allowed=False)
    response = denied_origin.validate(raw_request(credential))
    assert response.safe_error.code == "origin_not_allowed"
    assert "public_session.created" not in [event.event_type for event in denied_origin.event_sink.events]


def test_gateway_validation_can_consume_message_without_rag_or_public_route(db: Session) -> None:
    credential = seed_public_credential(db)
    gateway = make_gateway(db, credential)
    created = gateway.validate(raw_request(credential))
    token = created.payload["public_session_token"]

    validated = gateway.validate_access(raw_request(credential, session_operation="session_validation", public_session_token=token, rate_limit_category="widget_message_send", consume_message_slot=True))

    assert validated.response.status == "validated"
    assert validated.context.session_id is not None
    assert validated.response.payload["remaining_messages"] == 29
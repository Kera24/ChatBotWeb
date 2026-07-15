from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.errors import PublicAccessError
from app.access.messages.contracts import PublicMessageInput
from app.access.messages.idempotency import PublicMessageIdempotencyService, canonical_request_hash, hash_idempotency_key, validate_idempotency_key
from app.access.messages.preparation import PublicMessagePreparationService
from app.access.channels.widget import WidgetChannelAdapter
from app.access.messages.validation import normalise_message, validate_message_metadata
from app.access.observability.events import InMemoryAccessEventSink
from app.access.sessions.contracts import CreatePublicSessionCommand
from app.access.sessions.service import PublicSessionChecks, PublicSessionService
from app.access.credentials.contracts import CredentialRecord
from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, Organisation, PublicCredential, PublicMessageRequest, PublicSession, Workspace

NOW = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)
TOKEN_SECRET = "unit-public-session-secret"
VALID_IDEMPOTENCY_KEY = "idem-key-1234567890"
ORIGIN = "https://example.test"


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    with TestingSession() as session:
        yield session
    Base.metadata.drop_all(engine)


def seed_public_credential(db: Session, *, credential_status: str = "active", org_status: str = "active", workspace_status: str = "active") -> PublicCredential:
    org = Organisation(name="Alpha Org", slug=f"alpha-{uuid4().hex[:8]}", status=org_status)
    workspace = Workspace(organisation=org, name="Knowledge", slug=f"knowledge-{uuid4().hex[:8]}", status=workspace_status)
    credential = PublicCredential(
        organisation_id="pending",
        workspace_id="pending",
        credential_type="widget_public_key",
        public_identifier=f"wpk_dev_{uuid4().hex}",
        display_name="Widget",
        status=credential_status,
        environment="development",
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


def credential_record(row: PublicCredential) -> CredentialRecord:
    return CredentialRecord(
        credential_id=row.id,
        organisation_id=row.organisation_id,
        workspace_id=row.workspace_id,
        credential_type=row.credential_type,
        public_identifier=row.public_identifier,
        status=row.status,
        environment=row.environment,
        policy_profile=row.policy_profile,
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


def create_session(db: Session, credential: PublicCredential, *, max_messages: int = 3, now: datetime = NOW) -> tuple[PublicSessionService, str]:
    service = session_service(db, credential, now=now)
    created = service.create_session(
        CreatePublicSessionCommand(
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            credential_id=credential.id,
            channel="widget",
            environment=credential.environment,
            policy_profile="widget",
            origin_id="origin-1",
            canonical_origin=ORIGIN,
            inactivity_timeout_seconds=1800,
            absolute_lifetime_seconds=86400,
            max_messages=max_messages,
            metadata={"source": "unit"},
            request_id="req-create",
            trace_id="trace-create",
            received_at=now,
        )
    )
    return service, created.public_session_token


def message_input(token: str, *, message: str = "  Hello\r\nworld Ã¢Ëœâ€¢  ", key: str = VALID_IDEMPOTENCY_KEY, metadata: dict | None = None) -> PublicMessageInput:
    return PublicMessageInput(
        session_token=token,
        message=message,
        idempotency_key=key,
        client_request_id="client-1",
        metadata=metadata or {"intent": "support"},
        request_id="req-msg",
        trace_id="trace-msg",
        received_at=NOW + timedelta(minutes=1),
    )


def preparation_service(db: Session, public_session_service: PublicSessionService, event_sink: InMemoryAccessEventSink | None = None) -> PublicMessagePreparationService:
    return PublicMessagePreparationService(
        db=db,
        public_session_service=public_session_service,
        event_sink=event_sink or InMemoryAccessEventSink(),
        clock=lambda: NOW + timedelta(minutes=1),
    )


def prepare(db: Session, credential: PublicCredential, token: str, service: PublicMessagePreparationService, command: PublicMessageInput):
    return service.prepare(
        command,
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        credential_id=credential.id,
        channel="widget",
        environment=credential.environment,
        policy_profile="widget",
        canonical_origin=ORIGIN,
        max_messages=3,
        inactivity_timeout_seconds=1800,
    )


def test_message_validation_normalises_unicode_and_rejects_unsafe_inputs() -> None:
    assert normalise_message("  Hello\r\nworld Ã¢Ëœâ€¢  ") == "Hello\nworld Ã¢Ëœâ€¢"
    with pytest.raises(PublicAccessError) as empty:
        normalise_message(" \n\t ")
    assert empty.value.code == "invalid_message"
    with pytest.raises(PublicAccessError) as nul:
        normalise_message("hello\x00world")
    assert nul.value.code == "invalid_message"
    with pytest.raises(PublicAccessError) as byte_limit:
        normalise_message("Ã°Å¸â„¢â€š" * 4000)
    assert byte_limit.value.code == "message_too_large"
    with pytest.raises(PublicAccessError) as forbidden:
        validate_message_metadata({"conversation_id": "client-choice"})
    assert forbidden.value.code == "invalid_request"
    with pytest.raises(PublicAccessError):
        validate_message_metadata({f"k{i}": i for i in range(20)})


def test_idempotency_key_hash_and_request_hash_are_stable_and_safe() -> None:
    assert validate_idempotency_key(VALID_IDEMPOTENCY_KEY) == VALID_IDEMPOTENCY_KEY
    digest = hash_idempotency_key(VALID_IDEMPOTENCY_KEY, secret="unit-secret")
    assert digest == hash_idempotency_key(VALID_IDEMPOTENCY_KEY, secret="unit-secret")
    assert VALID_IDEMPOTENCY_KEY not in digest
    first = canonical_request_hash(canonical_message="hello", metadata={"a": 1}, public_session_id="session-1")
    second = canonical_request_hash(canonical_message="hello", metadata={"a": 1}, public_session_id="session-1")
    changed = canonical_request_hash(canonical_message="hello!", metadata={"a": 1}, public_session_id="session-1")
    assert first == second
    assert first != changed
    for bad in [None, "", "short", "contains space value", "x" * 200]:
        with pytest.raises(PublicAccessError):
            validate_idempotency_key(bad)  # type: ignore[arg-type]


def test_idempotency_service_converges_duplicates_and_conflicts(db: Session) -> None:
    credential = seed_public_credential(db)
    public_session_service, token = create_session(db, credential)
    prep = preparation_service(db, public_session_service)
    first = prepare(db, credential, token, prep, message_input(token))
    assert first.idempotency.state == "new"
    assert first.prepared is not None
    record = db.get(PublicMessageRequest, first.prepared.idempotency_record_id)
    assert record is not None
    assert record.status == "processing"
    assert record.idempotency_key_hash != VALID_IDEMPOTENCY_KEY
    assert VALID_IDEMPOTENCY_KEY not in str(record.__dict__)

    duplicate = prepare(db, credential, token, prep, message_input(token))
    assert duplicate.idempotency.state == "processing"
    assert duplicate.prepared is None

    idem = PublicMessageIdempotencyService(db=db)
    completed = idem.mark_completed(
        record_id=record.id,
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        response_snapshot={"answer": "cached", "remaining_messages": 2},
        now=NOW + timedelta(minutes=2),
    )
    assert completed.state == "completed"
    completed_duplicate = prepare(db, credential, token, prep, message_input(token))
    assert completed_duplicate.idempotency.state == "completed"
    assert completed_duplicate.idempotency.stored_response == {"answer": "cached", "remaining_messages": 2}

    conflict = prepare(db, credential, token, prep, message_input(token, message="different message"))
    assert conflict.idempotency.state == "conflict"
    assert conflict.idempotency.safe_error_code == "idempotency_conflict"


def test_preparation_creates_conversation_consumes_one_slot_and_creates_no_messages(db: Session) -> None:
    credential = seed_public_credential(db)
    public_session_service, token = create_session(db, credential)
    event_sink = InMemoryAccessEventSink()
    prep = preparation_service(db, public_session_service, event_sink=event_sink)

    result = prepare(db, credential, token, prep, message_input(token))

    assert result.idempotency.state == "new"
    assert result.prepared is not None
    assert result.prepared.canonical_message == "Hello\nworld Ã¢Ëœâ€¢"
    assert result.prepared.remaining_messages == 2
    session = db.execute(select(PublicSession)).scalar_one()
    assert session.message_count == 1
    assert session.conversation_id == result.prepared.conversation_id
    conversation = db.get(ChatSession, result.prepared.conversation_id)
    assert conversation is not None
    assert conversation.channel == "widget"
    assert db.execute(select(ChatMessage)).scalars().all() == []
    event_types = [event.event_type for event in event_sink.events]
    assert "widget.message.slot_consumed" in event_types
    assert "widget.message.preparation_completed" in event_types


def test_duplicate_processing_conflict_and_validation_failures_do_not_consume_slots(db: Session) -> None:
    credential = seed_public_credential(db)
    public_session_service, token = create_session(db, credential)
    prep = preparation_service(db, public_session_service)
    first = prepare(db, credential, token, prep, message_input(token))
    assert first.prepared is not None
    session = db.execute(select(PublicSession)).scalar_one()
    assert session.message_count == 1

    duplicate = prepare(db, credential, token, prep, message_input(token))
    assert duplicate.idempotency.state == "processing"
    assert session.message_count == 1

    conflict = prepare(db, credential, token, prep, message_input(token, message="different message"))
    assert conflict.idempotency.state == "conflict"
    assert session.message_count == 1

    with pytest.raises(PublicAccessError) as origin_mismatch:
        prep.prepare(
            message_input(token, key="another-key-123456"),
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            credential_id=credential.id,
            channel="widget",
            environment=credential.environment,
            policy_profile="widget",
            canonical_origin="https://evil.example",
            max_messages=3,
            inactivity_timeout_seconds=1800,
        )
    assert origin_mismatch.value.code == "session_origin_mismatch"
    assert session.message_count == 1


def test_message_cap_exhaustion_fails_before_new_slot(db: Session) -> None:
    credential = seed_public_credential(db)
    public_session_service, token = create_session(db, credential, max_messages=1)
    prep = preparation_service(db, public_session_service)
    result = prep.prepare(
        message_input(token),
        organisation_id=credential.organisation_id,
        workspace_id=credential.workspace_id,
        credential_id=credential.id,
        channel="widget",
        environment=credential.environment,
        policy_profile="widget",
        canonical_origin=ORIGIN,
        max_messages=1,
        inactivity_timeout_seconds=1800,
    )
    assert result.prepared is not None
    with pytest.raises(PublicAccessError) as exhausted:
        prep.prepare(
            message_input(token, key="second-key-123456"),
            organisation_id=credential.organisation_id,
            workspace_id=credential.workspace_id,
            credential_id=credential.id,
            channel="widget",
            environment=credential.environment,
            policy_profile="widget",
            canonical_origin=ORIGIN,
            max_messages=1,
            inactivity_timeout_seconds=1800,
        )
    assert exhausted.value.code == "session_limit_reached"
    session = db.execute(select(PublicSession)).scalar_one()
    assert session.message_count == 1


def test_widget_adapter_internal_message_send_shape_and_dashboard_headers() -> None:
    adapter = WidgetChannelAdapter()
    parsed = {
        "access_operation": "message_send",
        "method": "POST",
        "public_key": "wpk_dev_public",
        "body": {"session_token": "pss_dev_token.secret", "message": "hello", "metadata": {"topic": "support"}},
        "headers": {},
    }
    adapter.validate_request_shape(parsed)
    assert adapter.extract_session_token(parsed) == "pss_dev_token.secret"
    assert adapter.normalise_message(parsed) == "hello"

    parsed_with_dashboard_header = dict(parsed)
    parsed_with_dashboard_header["headers"] = {"X-Development-User-Email": "admin@example.test"}
    with pytest.raises(PublicAccessError) as rejected:
        adapter.validate_request_shape(parsed_with_dashboard_header)
    assert rejected.value.code == "invalid_request"
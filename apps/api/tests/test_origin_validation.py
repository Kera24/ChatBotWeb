from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.access.channels.base import DevelopmentTestChannelAdapter
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import InMemoryCredentialRegistry
from app.access.errors import PublicAccessError
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import InMemoryAccessEventSink
from app.access.origin_validation.contracts import AllowedOriginRecord, OriginValidationRequest
from app.access.origin_validation.matcher import match_origin
from app.access.origin_validation.normalisation import normalise_origin_header
from app.access.origin_validation.repository import get_origin_for_credential_scope, list_active_origins_for_credential
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.models import AccessPolicyProfile, planned_partner_api_policy, planned_widget_policy
from app.access.policies.registry import AccessPolicyRegistry, default_policy_registry
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks
from app.db.base import Base
from app.db.models import CredentialAllowedOrigin, Organisation, PublicCredential, User, Workspace


def policy(*, key: str = "widget", origin_required: bool = True) -> AccessPolicyProfile:
    base = planned_widget_policy()
    return AccessPolicyProfile(
        policy_key=key,
        max_request_bytes=base.max_request_bytes,
        max_message_characters=base.max_message_characters,
        session_lifetime_seconds=base.session_lifetime_seconds,
        max_messages_per_session=base.max_messages_per_session,
        retrieval_limit=base.retrieval_limit,
        max_context_characters=base.max_context_characters,
        max_output_tokens=base.max_output_tokens,
        request_timeout_seconds=base.request_timeout_seconds,
        origin_required=origin_required,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=base.allowed_model_keys,
        retention_days=base.retention_days,
    )


def origin_record(
    *,
    origin_id: str = "origin-1",
    credential_id: str = "cred-1",
    scheme: str = "https",
    hostname: str = "example.com",
    port: int | None = None,
    wildcard_subdomains: bool = False,
    environment: str = "production",
    active: bool = True,
) -> AllowedOriginRecord:
    return AllowedOriginRecord(
        origin_id=origin_id,
        credential_id=credential_id,
        scheme=scheme,
        hostname=hostname,
        port=port,
        wildcard_subdomains=wildcard_subdomains,
        environment=environment,
        active=active,
    )


def validation_request(**overrides) -> OriginValidationRequest:
    values = {
        "credential_id": "cred-1",
        "credential_environment": "production",
        "credential_type": "widget_public_key",
        "policy_profile": policy(),
        "origin_header": "https://example.com",
        "referer_header": None,
        "request_method": "POST",
        "channel": "widget",
        "trusted_proxy_context": None,
        "request_id": "req-1",
        "trace_id": "trace-1",
    }
    values.update(overrides)
    return OriginValidationRequest(**values)


@pytest.mark.parametrize(
    ("raw", "serialised", "hostname", "port"),
    [
        ("HTTPS://Example.COM", "https://example.com:443", "example.com", 443),
        ("http://example.com", "http://example.com:80", "example.com", 80),
        ("https://example.com:8443", "https://example.com:8443", "example.com", 8443),
        ("https://example.com.", "https://example.com:443", "example.com", 443),
        ("https://bücher.example", "https://xn--bcher-kva.example:443", "xn--bcher-kva.example", 443),
        ("http://127.0.0.1:3000", "http://127.0.0.1:3000", "127.0.0.1", 3000),
        ("http://[::1]:3000", "http://[::1]:3000", "::1", 3000),
        ("http://localhost:3000", "http://localhost:3000", "localhost", 3000),
    ],
)
def test_origin_normalisation_canonicalises_safe_origins(raw, serialised, hostname, port):
    origin = normalise_origin_header(raw)

    assert origin.serialised == serialised
    assert origin.hostname == hostname
    assert origin.effective_port == port


@pytest.mark.parametrize(
    "raw",
    [
        "https://example.com/path",
        "https://example.com?x=1",
        "https://example.com#frag",
        "https://user@example.com",
        "ftp://example.com",
        "https:///missing-host",
        "http://[::1",
        "https://bad\udcff.example",
    ],
)
def test_origin_normalisation_rejects_unsafe_or_malformed_origins(raw):
    with pytest.raises(Exception):
        normalise_origin_header(raw)


def test_origin_normalisation_marks_loopback_and_ip_addresses():
    ipv4 = normalise_origin_header("http://127.10.20.30:8080")
    ipv6 = normalise_origin_header("http://[::1]:8080")
    localhost = normalise_origin_header("http://localhost:3000")

    assert ipv4.is_ip_address is True and ipv4.is_loopback is True
    assert ipv6.is_ip_address is True and ipv6.is_loopback is True
    assert localhost.is_ip_address is False and localhost.is_loopback is True


@pytest.mark.parametrize(
    ("raw", "records", "expected_match"),
    [
        ("https://example.com", [origin_record()], "exact"),
        ("http://example.com", [origin_record()], "none"),
        ("https://example.com:444", [origin_record()], "none"),
        ("https://other.com", [origin_record()], "none"),
        ("https://app.example.com", [origin_record(wildcard_subdomains=True)], "wildcard"),
        ("https://example.com", [origin_record(wildcard_subdomains=True)], "none"),
        ("https://a.b.example.com", [origin_record(wildcard_subdomains=True)], "none"),
        ("https://evil-example.com", [origin_record(wildcard_subdomains=True)], "none"),
        ("https://example.com.evil.org", [origin_record(wildcard_subdomains=True)], "none"),
        ("https://app.example.com", [origin_record(wildcard_subdomains=True, scheme="http")], "none"),
        ("https://app.example.com", [origin_record(wildcard_subdomains=True, port=444)], "none"),
    ],
)
def test_origin_matching_exact_and_wildcard_rules(raw, records, expected_match):
    match_type, matched = match_origin(normalise_origin_header(raw), records, environment="production")

    assert match_type == expected_match
    assert (matched is not None) == (expected_match != "none")


@pytest.mark.parametrize(
    "record",
    [
        origin_record(hostname="127.0.0.1", wildcard_subdomains=True),
        origin_record(hostname="localhost", wildcard_subdomains=True),
        origin_record(hostname="com", wildcard_subdomains=True),
        origin_record(hostname="co.uk", wildcard_subdomains=True),
    ],
)
def test_origin_matching_rejects_forbidden_wildcard_records(record):
    match_type, matched = match_origin(normalise_origin_header("https://app.example.com"), [record], environment="production")

    assert match_type == "none"
    assert matched is None


def test_origin_matching_rejects_environment_mismatch_and_allows_development_loopback():
    mismatch, _ = match_origin(
        normalise_origin_header("https://example.com"),
        [origin_record(environment="development")],
        environment="production",
    )
    loopback, matched = match_origin(
        normalise_origin_header("http://localhost:3000"),
        [origin_record(scheme="http", hostname="localhost", port=3000, environment="development")],
        environment="development",
    )

    assert mismatch == "none"
    assert loopback == "development_loopback"
    assert matched is not None


def test_origin_service_allows_active_configured_origin_and_emits_event():
    events = InMemoryAccessEventSink()
    service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: [origin_record()], event_sink=events)

    result = service.validate(validation_request())

    assert result.allowed is True
    assert result.match_type == "exact"
    assert events.events[-1].event_type == "origin.validation.allowed"
    assert "https://example.com" not in str([event.to_dict() for event in events.events])


def test_origin_service_rejects_disallowed_origin_safely_without_origin_list_leak():
    service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: [origin_record(hostname="allowed.example")])

    with pytest.raises(PublicAccessError) as exc:
        service.validate(validation_request(origin_header="https://denied.example"))

    public = exc.value.to_public_dict()
    assert public["code"] == "origin_not_allowed"
    assert "allowed.example" not in str(public)


def test_origin_service_rejects_missing_origin_for_widget_policy():
    service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: [])

    with pytest.raises(PublicAccessError) as exc:
        service.validate(validation_request(origin_header=None))

    assert exc.value.code == "origin_required"


def test_origin_service_partner_api_bypasses_browser_origin_by_policy():
    service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: [])

    result = service.validate(
        validation_request(
            credential_type="partner_api_key",
            policy_profile=planned_partner_api_policy(),
            origin_header=None,
        )
    )

    assert result.allowed is True
    assert result.reason_code == "not_applicable"


def test_origin_service_ignores_inactive_and_other_credential_origins():
    service = OriginValidationService(
        origin_lookup=lambda _credential_id, _environment: [
            origin_record(active=False),
            origin_record(credential_id="other", hostname="example.com"),
        ]
    )

    with pytest.raises(PublicAccessError) as exc:
        service.validate(validation_request())

    assert exc.value.code == "origin_not_allowed"


def test_origin_service_rejects_malformed_and_insecure_production_origins():
    service = OriginValidationService(origin_lookup=lambda _credential_id, _environment: [origin_record()])

    with pytest.raises(PublicAccessError) as malformed:
        service.validate(validation_request(origin_header="https://example.com/path"))
    with pytest.raises(PublicAccessError) as insecure:
        service.validate(validation_request(origin_header="http://example.com"))

    assert malformed.value.code == "malformed_origin"
    assert insecure.value.code == "insecure_origin"


def test_origin_repository_reads_are_credential_and_tenant_scoped():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        org = Organisation(name="Alpha", slug="alpha", status="active")
        user = User(email="admin@example.test")
        workspace = Workspace(organisation=org, name="Knowledge", slug="knowledge", status="active")
        db.add_all([org, user, workspace])
        db.flush()
        credential = PublicCredential(
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_type="widget_public_key",
            public_identifier="wpk_dev_test",
            display_name="Widget",
            status="active",
            environment="development",
            policy_profile="widget",
            capabilities_json=["widget_chat"],
            created_by_user_id=user.id,
        )
        db.add(credential)
        db.flush()
        active = CredentialAllowedOrigin(
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_id=credential.id,
            scheme="http",
            hostname="localhost",
            port=3000,
            wildcard_subdomains=False,
            environment="development",
            active=True,
        )
        inactive = CredentialAllowedOrigin(
            organisation_id=org.id,
            workspace_id=workspace.id,
            credential_id=credential.id,
            scheme="https",
            hostname="inactive.example",
            port=None,
            wildcard_subdomains=False,
            environment="development",
            active=False,
        )
        db.add_all([active, inactive])
        db.commit()

        records = list_active_origins_for_credential(db, credential_id=credential.id, environment="development")
        fetched = get_origin_for_credential_scope(db, organisation_id=org.id, workspace_id=workspace.id, credential_id=credential.id, origin_id=active.id)
        cross_tenant = get_origin_for_credential_scope(db, organisation_id="other", workspace_id=workspace.id, credential_id=credential.id, origin_id=active.id)

    assert [record.origin_id for record in records] == [active.id]
    assert fetched is not None and fetched.hostname == "localhost"
    assert cross_tenant is None


def gateway_record(*, policy_profile: str = "widget", credential_type: str = "widget_public_key") -> CredentialRecord:
    return CredentialRecord(
        credential_id="cred-1",
        organisation_id="org-1",
        workspace_id="workspace-1",
        credential_type=credential_type,
        public_identifier="public-test",
        status="active",
        environment="production",
        capabilities=("widget_chat",),
        policy_profile=policy_profile,
        created_at=datetime.now(timezone.utc),
    )


def make_gateway_with_origin_service(*, records=None, origin_lookup=None):
    credential_registry = InMemoryCredentialRegistry(records or [gateway_record()])
    policy_registry = default_policy_registry()
    tenant_service = PublicTenantResolutionService(
        credential_registry=credential_registry,
        policy_registry=policy_registry,
        checks=TenantResolutionChecks(
            organisation_is_active=lambda _organisation_id: True,
            workspace_is_active=lambda _workspace_id: True,
            workspace_belongs_to_organisation=lambda _workspace_id, _organisation_id: True,
        ),
    )
    event_sink = InMemoryAccessEventSink()
    origin_service = OriginValidationService(origin_lookup=origin_lookup or (lambda _credential_id, _environment: [origin_record()]), event_sink=event_sink)
    return PublicAccessGateway(
        channel_registry=ChannelRegistry([DevelopmentTestChannelAdapter()]),
        tenant_resolution_service=tenant_service,
        policy_registry=policy_registry,
        event_sink=event_sink,
        origin_validation_service=origin_service,
    ), event_sink


def raw_gateway_request(**overrides):
    request = {
        "request_id": "req-1",
        "channel": "internal_test",
        "credential_type": "widget_public_key",
        "public_identifier": "public-test",
        "origin": "https://example.com",
        "message": "Hello",
    }
    request.update(overrides)
    return request


def test_gateway_invokes_origin_validation_and_stops_before_rag():
    gateway, events = make_gateway_with_origin_service()

    result = gateway.validate_access(raw_gateway_request())

    assert result.response.status == "validated"
    assert "origin.validation.allowed" in [event.event_type for event in events.events]
    assert result.response.payload == {"message": "Hello"}


def test_gateway_rejects_missing_origin_when_widget_policy_requires_it():
    gateway, _events = make_gateway_with_origin_service()

    response = gateway.validate(raw_gateway_request(origin=None))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "origin_required"


def test_gateway_internal_test_policy_remains_test_only_and_can_skip_origin():
    record = gateway_record(policy_profile="internal_test")
    gateway, events = make_gateway_with_origin_service(records=[record], origin_lookup=lambda _credential_id, _environment: [])

    response = gateway.validate(raw_gateway_request(origin=None))

    assert response.status == "validated"
    assert "origin.validation.development_exception" in [event.event_type for event in events.events]


def test_gateway_partner_api_policy_bypasses_origin_without_accepting_dashboard_headers():
    record = gateway_record(policy_profile="partner_api", credential_type="partner_api_key")
    gateway, _events = make_gateway_with_origin_service(records=[record], origin_lookup=lambda _credential_id, _environment: [])

    accepted = gateway.validate(raw_gateway_request(credential_type="partner_api_key", origin=None))
    rejected = gateway.validate(raw_gateway_request(credential_type="partner_api_key", origin=None, headers={"X-Development-Role": "org_owner"}))

    assert accepted.status == "validated"
    assert rejected.status == "rejected"
    assert rejected.safe_error is not None
    assert rejected.safe_error.code == "unsafe_request"

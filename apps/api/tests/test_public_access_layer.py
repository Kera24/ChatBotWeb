from datetime import datetime, timedelta, timezone

import pytest

from app.access.channels.base import DevelopmentTestChannelAdapter
from app.access.contracts import (
    PublicAccessRequest,
    PublicAccessResponse,
    PublicCredentialReference,
)
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import DuplicateCredentialError, InMemoryCredentialRegistry
from app.access.errors import PublicAccessError, error_detail
from app.access.gateway import ChannelRegistry, DuplicateChannelError, PublicAccessGateway
from app.access.observability.events import InMemoryAccessEventSink
from app.access.policies.models import AccessPolicyProfile
from app.access.policies.registry import AccessPolicyRegistry, DuplicatePolicyError, default_policy_registry
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks
from app.main import create_app


def credential_record(
    *,
    public_identifier: str = "public-test",
    credential_id: str = "cred-1",
    organisation_id: str = "org-1",
    workspace_id: str = "workspace-1",
    status: str = "active",
    expires_at: datetime | None = None,
) -> CredentialRecord:
    return CredentialRecord(
        credential_id=credential_id,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        credential_type="widget_public_key",
        public_identifier=public_identifier,
        secret_hash="hashed-secret",
        status=status,
        environment="development",
        allowed_origins=("http://localhost:3000",),
        capabilities=("message",),
        policy_profile="internal_test",
        expires_at=expires_at,
    )


def raw_request(**overrides):
    request = {
        "request_id": "req-1",
        "channel": "internal_test",
        "credential_type": "widget_public_key",
        "public_identifier": "public-test",
        "message": "How do I use this?",
        "channel_metadata": {"source": "unit-test"},
    }
    request.update(overrides)
    return request


def make_gateway(
    *,
    record: CredentialRecord | None = None,
    org_active: bool = True,
    workspace_active: bool = True,
    belongs: bool = True,
):
    credential_registry = InMemoryCredentialRegistry([record or credential_record()])
    policy_registry = default_policy_registry()
    checks = TenantResolutionChecks(
        organisation_is_active=lambda _organisation_id: org_active,
        workspace_is_active=lambda _workspace_id: workspace_active,
        workspace_belongs_to_organisation=lambda _workspace_id, _organisation_id: belongs,
    )
    tenant_service = PublicTenantResolutionService(
        credential_registry=credential_registry,
        policy_registry=policy_registry,
        checks=checks,
    )
    event_sink = InMemoryAccessEventSink()
    gateway = PublicAccessGateway(
        channel_registry=ChannelRegistry([DevelopmentTestChannelAdapter()]),
        tenant_resolution_service=tenant_service,
        policy_registry=policy_registry,
        event_sink=event_sink,
    )
    return gateway, event_sink


def test_public_request_serialises_without_trusted_tenant_fields():
    request = PublicAccessRequest(
        request_id="req-1",
        channel="internal_test",
        public_credential=PublicCredentialReference(
            credential_type="widget_public_key",
            public_identifier="public-test",
        ),
        message="hello",
    )

    data = request.to_dict()

    assert data["channel"] == "internal_test"
    assert "organisation_id" not in data
    assert "workspace_id" not in data
    with pytest.raises(TypeError):
        PublicAccessRequest(  # type: ignore[call-arg]
            request_id="req-1",
            channel="internal_test",
            public_credential=request.public_credential,
            message="hello",
            organisation_id="fake-org",
        )


def test_safe_public_response_and_error_serialise_without_internals():
    detail = error_detail("rate_limited", retry_after_seconds=30)
    response = PublicAccessResponse(
        request_id="req-1",
        trace_id="trace-1",
        status="rejected",
        safe_error=detail,
    )

    data = response.to_dict()

    assert data["safe_error"] == {
        "code": "rate_limited",
        "message": "Too many requests. Try again later.",
        "retryable": True,
        "http_status": 429,
        "retry_after_seconds": 30,
    }
    assert "org-" not in str(data)
    assert "workspace-" not in str(data)
    assert "stack" not in str(data).lower()


@pytest.mark.parametrize(
    "metadata",
    [
        {f"k{i}": "v" for i in range(21)},
        {"k" * 81: "v"},
        {"key": "v" * 501},
        {"nested": {"unsafe": True}},
    ],
)
def test_metadata_is_bounded_and_scalar(metadata):
    with pytest.raises(ValueError):
        PublicAccessRequest(
            request_id="req-1",
            channel="internal_test",
            public_credential=PublicCredentialReference("widget_public_key", "public-test"),
            message="hello",
            channel_metadata=metadata,
        )


def test_channel_registry_registers_and_resolves_adapter():
    adapter = DevelopmentTestChannelAdapter()
    registry = ChannelRegistry([adapter])

    assert registry.resolve("internal_test") is adapter


def test_channel_registry_rejects_duplicate_adapter():
    registry = ChannelRegistry([DevelopmentTestChannelAdapter()])

    with pytest.raises(DuplicateChannelError):
        registry.register(DevelopmentTestChannelAdapter())


def test_channel_registry_unsupported_channel_returns_safe_error():
    registry = ChannelRegistry()

    with pytest.raises(PublicAccessError) as exc:
        registry.resolve("widget")

    assert exc.value.code == "unsupported_channel"


def test_credential_registry_resolves_active_credential_without_secret_material():
    record = credential_record()
    registry = InMemoryCredentialRegistry([record])

    resolved = registry.resolve("public-test")

    assert resolved.credential_id == "cred-1"
    assert "secret_hash" not in resolved.public_dict()


def test_credential_registry_rejects_duplicate_public_identifier():
    with pytest.raises(DuplicateCredentialError):
        InMemoryCredentialRegistry([credential_record(), credential_record(credential_id="cred-2")])


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("disabled", "disabled_credential"),
        ("revoked", "invalid_credential"),
        ("expired", "expired_credential"),
    ],
)
def test_credential_registry_rejects_unusable_statuses(status, expected_code):
    registry = InMemoryCredentialRegistry([credential_record(status=status)])

    with pytest.raises(PublicAccessError) as exc:
        registry.resolve("public-test")

    assert exc.value.code == expected_code


def test_credential_registry_rejects_expired_active_credential():
    registry = InMemoryCredentialRegistry(
        [credential_record(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))]
    )

    with pytest.raises(PublicAccessError) as exc:
        registry.resolve("public-test")

    assert exc.value.code == "expired_credential"


def test_policy_registry_registration_resolution_and_duplicates():
    profile = AccessPolicyProfile(
        policy_key="tiny",
        max_request_bytes=64,
        max_message_characters=16,
        session_lifetime_seconds=60,
        max_messages_per_session=2,
        retrieval_limit=1,
        max_context_characters=100,
        max_output_tokens=20,
        request_timeout_seconds=3,
        origin_required=False,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=("mock-grounded-answer",),
        retention_days=1,
    )
    registry = AccessPolicyRegistry([profile])

    assert registry.resolve("tiny") is profile
    default_registry = default_policy_registry()
    assert default_registry.resolve("internal_test").policy_key == "internal_test"
    assert default_registry.resolve("widget").policy_key == "widget"
    assert default_registry.resolve("partner_api").policy_key == "partner_api"
    with pytest.raises(DuplicatePolicyError):
        registry.register(profile)


def test_policy_profile_rejects_invalid_limits():
    with pytest.raises(ValueError):
        AccessPolicyProfile(
            policy_key="bad",
            max_request_bytes=0,
            max_message_characters=10,
            session_lifetime_seconds=60,
            max_messages_per_session=1,
            retrieval_limit=1,
            max_context_characters=1,
            max_output_tokens=1,
            request_timeout_seconds=1,
            origin_required=False,
            fail_closed_on_rate_limit_store_failure=True,
            allowed_model_keys=("mock",),
            retention_days=1,
        )


def test_tenant_resolution_uses_credential_tenant_context_only():
    credential_registry = InMemoryCredentialRegistry([credential_record()])
    policy_registry = default_policy_registry()
    service = PublicTenantResolutionService(
        credential_registry=credential_registry,
        policy_registry=policy_registry,
        checks=TenantResolutionChecks(
            organisation_is_active=lambda _organisation_id: True,
            workspace_is_active=lambda _workspace_id: True,
            workspace_belongs_to_organisation=lambda _workspace_id, _organisation_id: True,
        ),
    )
    request = PublicAccessRequest(
        request_id="req-1",
        channel="internal_test",
        public_credential=PublicCredentialReference("widget_public_key", "public-test"),
        message="hello",
        channel_metadata={"organisation_id": "fake-org", "workspace_id": "fake-workspace"},
    )

    context, _record = service.resolve(request)

    assert context.organisation_id == "org-1"
    assert context.workspace_id == "workspace-1"
    assert context.policy_profile == "internal_test"


@pytest.mark.parametrize(
    ("org_active", "workspace_active", "belongs", "expected_code"),
    [
        (False, True, True, "disabled_credential"),
        (True, False, True, "disabled_credential"),
        (True, True, False, "invalid_credential"),
    ],
)
def test_tenant_resolution_rejects_inactive_or_mismatched_tenant(org_active, workspace_active, belongs, expected_code):
    gateway, _events = make_gateway(org_active=org_active, workspace_active=workspace_active, belongs=belongs)

    response = gateway.validate(raw_request())

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == expected_code


def test_gateway_successful_validation_path_emits_safe_events():
    gateway, events = make_gateway()

    result = gateway.validate_access(raw_request())

    assert result.response.status == "validated"
    assert result.context.organisation_id == "org-1"
    assert result.context.workspace_id == "workspace-1"
    assert result.response.payload == {"message": "How do I use this?"}
    assert [event.event_type for event in events.events] == [
        "access.request.received",
        "access.channel.resolved",
        "access.credential.resolved",
        "access.tenant.resolved",
        "access.request.validated",
    ]
    assert "How do I use this?" not in str([event.to_dict() for event in events.events])


def test_gateway_rejects_unsupported_channel():
    gateway, _events = make_gateway()

    response = gateway.validate(raw_request(channel="widget"))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "unsupported_channel"


def test_gateway_rejects_invalid_credential():
    gateway, _events = make_gateway()

    response = gateway.validate(raw_request(public_identifier="missing"))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "invalid_credential"


def test_gateway_rejects_message_too_large():
    gateway, _events = make_gateway()

    response = gateway.validate(raw_request(message="x" * 501))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "message_too_large"


def test_gateway_rejects_empty_message():
    gateway, _events = make_gateway()

    response = gateway.validate(raw_request(message="   "))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "unsafe_request"


def test_gateway_rejects_invalid_metadata():
    gateway, _events = make_gateway()

    response = gateway.validate(raw_request(channel_metadata={"nested": {"unsafe": True}}))

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "unsafe_request"


def test_gateway_safe_errors_do_not_leak_tenant_ids_or_internals():
    gateway, _events = make_gateway(belongs=False)

    response = gateway.validate(raw_request())
    data = response.to_dict()

    assert response.safe_error is not None
    assert "org-1" not in str(data)
    assert "workspace-1" not in str(data)
    assert "hashed-secret" not in str(data)
    assert "traceback" not in str(data).lower()


def test_gateway_rejects_dashboard_development_headers():
    gateway, _events = make_gateway()

    response = gateway.validate(
        raw_request(headers={"X-Development-User-Email": "owner@example.com", "X-Development-Role": "org_owner"})
    )

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "unsafe_request"


def test_gateway_registries_are_isolated_across_tests():
    registry_with_adapter = ChannelRegistry([DevelopmentTestChannelAdapter()])
    empty_registry = ChannelRegistry()

    assert registry_with_adapter.resolve("internal_test").channel_key == "internal_test"
    with pytest.raises(PublicAccessError):
        empty_registry.resolve("internal_test")


def test_only_public_widget_session_route_is_added():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/api/v1/widget/{public_key}/sessions" in paths
    assert "/api/v1/widget/{public_key}/messages" not in paths
    assert "/api/v1/widget/{public_key}/config" in paths
    assert not any(path.startswith("/api/v1/public-access") for path in paths)

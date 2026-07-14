from datetime import datetime, timedelta, timezone

import pytest

from app.access.channels.base import DevelopmentTestChannelAdapter
from app.access.credentials.contracts import CredentialRecord
from app.access.credentials.registry import InMemoryCredentialRegistry
from app.access.errors import PublicAccessError
from app.access.gateway import ChannelRegistry, PublicAccessGateway
from app.access.observability.events import InMemoryAccessEventSink
from app.access.origin_validation.contracts import AllowedOriginRecord
from app.access.origin_validation.service import OriginValidationService
from app.access.policies.models import AccessPolicyProfile, planned_partner_api_policy, planned_widget_policy
from app.access.policies.registry import default_policy_registry
from app.access.rate_limit.client_ip import canonical_ip, extract_client_ip, parse_trusted_proxy_networks
from app.access.rate_limit.contracts import RateLimitRequest, RateLimitRule
from app.access.rate_limit.errors import RateLimitStoreError, RateLimitStoreTimeout
from app.access.rate_limit.identities import identity_for_rule, redis_rate_key, stable_hmac_identity
from app.access.rate_limit.local_fallback import LocalFallbackLimiter
from app.access.rate_limit.policies import validate_rate_limit_rules
from app.access.rate_limit.redis_store import InMemoryRateLimitStore
from app.access.rate_limit.service import EmergencyControls, RateLimitService
from app.access.rate_limit.token_bucket import evaluate_token_bucket, parse_redis_bucket_result
from app.access.tenant_resolution.service import PublicTenantResolutionService, TenantResolutionChecks

SECRET = "unit-test-rate-limit-secret"
NOW = datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc)


def rule(**overrides) -> RateLimitRule:
    values = {
        "rule_key": "credential_rule",
        "category": "widget_message_send",
        "dimension": "credential",
        "capacity": 3,
        "refill_tokens": 3,
        "refill_period_seconds": 60,
        "request_cost": 1,
        "enabled": True,
        "fail_mode": "fail_closed",
        "priority": 10,
        "retry_after_cap_seconds": 300,
    }
    values.update(overrides)
    return RateLimitRule(**values)


def policy_with_rules(*rules: RateLimitRule) -> AccessPolicyProfile:
    base = planned_widget_policy()
    return AccessPolicyProfile(
        policy_key="unit_policy",
        max_request_bytes=base.max_request_bytes,
        max_message_characters=base.max_message_characters,
        session_lifetime_seconds=base.session_lifetime_seconds,
        max_messages_per_session=base.max_messages_per_session,
        retrieval_limit=base.retrieval_limit,
        max_context_characters=base.max_context_characters,
        max_output_tokens=base.max_output_tokens,
        request_timeout_seconds=base.request_timeout_seconds,
        origin_required=base.origin_required,
        fail_closed_on_rate_limit_store_failure=True,
        allowed_model_keys=base.allowed_model_keys,
        retention_days=base.retention_days,
        rate_limit_rules=rules,
    )


def rate_request(**overrides) -> RateLimitRequest:
    values = {
        "request_id": "req-1",
        "trace_id": "trace-1",
        "environment": "production",
        "channel": "internal_test",
        "category": "widget_message_send",
        "credential_id": "cred-1",
        "organisation_id": "org-1",
        "workspace_id": "workspace-1",
        "client_ip_identity": "203.0.113.10",
        "session_id": "session-1",
        "policy_profile": policy_with_rules(rule()),
        "request_cost": 1,
        "received_at": NOW,
    }
    values.update(overrides)
    return RateLimitRequest(**values)


def test_token_bucket_initial_capacity_successful_consumption_and_ttl():
    result = evaluate_token_bucket(current_tokens=None, updated_at_seconds=None, now_seconds=NOW.timestamp(), rule=rule(capacity=5, refill_tokens=5), request_cost=2)

    assert result.allowed is True
    assert result.remaining == 3
    assert result.retry_after_seconds == 0
    assert result.ttl_seconds >= 120


def test_token_bucket_burst_exhaustion_retry_after_and_cost_greater_than_one():
    result = evaluate_token_bucket(current_tokens=1, updated_at_seconds=NOW.timestamp(), now_seconds=NOW.timestamp(), rule=rule(capacity=5, refill_tokens=5, refill_period_seconds=60), request_cost=3)

    assert result.allowed is False
    assert result.remaining == 1
    assert result.retry_after_seconds == 24


def test_token_bucket_deterministic_refill_and_capacity_cap():
    result = evaluate_token_bucket(current_tokens=4, updated_at_seconds=NOW.timestamp() - 120, now_seconds=NOW.timestamp(), rule=rule(capacity=5, refill_tokens=5, refill_period_seconds=60), request_cost=1)

    assert result.allowed is True
    assert result.remaining == 4


def test_token_bucket_script_result_parsing():
    parsed = parse_redis_bucket_result([1, 7, 0, 30, 120])

    assert parsed.allowed is True
    assert parsed.remaining == 7
    assert parsed.reset_after_seconds == 30


def test_in_memory_store_has_atomic_like_shared_state_for_unit_tests():
    store = InMemoryRateLimitStore()
    first = store.consume(key="k", rule=rule(capacity=1, refill_tokens=1), request_cost=1, now=NOW)
    second = store.consume(key="k", rule=rule(capacity=1, refill_tokens=1), request_cost=1, now=NOW)

    assert first.allowed is True
    assert second.allowed is False


def test_hmac_identity_and_safe_key_model_do_not_expose_raw_values():
    identity = stable_hmac_identity("203.0.113.10", secret=SECRET, purpose="ip")
    other = stable_hmac_identity("203.0.113.11", secret=SECRET, purpose="ip")
    key = redis_rate_key(prefix="rate", environment="production", dimension="ip", identity=identity, category="widget_message_send")

    assert identity == stable_hmac_identity("203.0.113.10", secret=SECRET, purpose="ip")
    assert identity != other
    assert "203.0.113.10" not in key
    assert key.startswith("rate:production:ip:")


def test_rule_identity_uses_environment_separated_keys_without_raw_credential():
    request = rate_request()
    identity = identity_for_rule(rule(dimension="credential"), request=request, secret=SECRET)
    prod_key = redis_rate_key(prefix="rate", environment="production", dimension="credential", identity=identity, category="widget_message_send")
    dev_key = redis_rate_key(prefix="rate", environment="development", dimension="credential", identity=identity, category="widget_message_send")

    assert prod_key != dev_key
    assert "cred-1" not in prod_key


def test_client_ip_canonicalisation_ipv4_ipv6_and_trusted_proxy_chain():
    networks = parse_trusted_proxy_networks("10.0.0.0/8, 2001:db8::/32")

    assert canonical_ip("203.0.113.010".replace("010", "10")) == "203.0.113.10"
    assert canonical_ip("2001:0db8::0001") == "2001:db8::1"
    result = extract_client_ip(peer_ip="10.0.0.5", headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.8"}, trusted_proxy_networks=networks)

    assert result.identity == "203.0.113.9"
    assert result.source == "x-forwarded-for"


def test_untrusted_forwarded_headers_are_ignored_and_spoofing_does_not_win():
    result = extract_client_ip(peer_ip="198.51.100.5", headers={"X-Forwarded-For": "203.0.113.9"}, trusted_proxy_networks=parse_trusted_proxy_networks("10.0.0.0/8"))

    assert result.identity == "198.51.100.5"
    assert result.source == "peer"


def test_malformed_forwarded_chain_rejected_under_trusted_proxy():
    with pytest.raises(ValueError):
        extract_client_ip(peer_ip="10.0.0.5", headers={"X-Forwarded-For": "not-an-ip"}, trusted_proxy_networks=parse_trusted_proxy_networks("10.0.0.0/8"))


def test_policy_rejects_duplicate_and_invalid_rules():
    with pytest.raises(ValueError):
        validate_rate_limit_rules((rule(rule_key="same"), rule(rule_key="same")))
    with pytest.raises(ValueError):
        RateLimitRule("bad", "widget_message_send", "credential", capacity=0, refill_tokens=1, refill_period_seconds=60)
    with pytest.raises(ValueError):
        RateLimitRule("bad", "widget_message_send", "credential", capacity=1, refill_tokens=1, refill_period_seconds=60, fail_mode="open")


def test_service_all_applicable_rules_pass_and_emit_event():
    events = InMemoryAccessEventSink()
    service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET, event_sink=events)

    decision = service.check(rate_request())

    assert decision.allowed is True
    assert events.events[-1].event_type == "rate_limit.allowed"
    assert "203.0.113.10" not in str([event.to_dict() for event in events.events])


@pytest.mark.parametrize("dimension", ["credential", "workspace", "ip", "global"])
def test_service_denies_by_dimension(dimension):
    limited_rule = rule(rule_key=f"{dimension}_rule", dimension=dimension, capacity=1, refill_tokens=1)
    request = rate_request(policy_profile=policy_with_rules(limited_rule))
    service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET)

    assert service.check(request).allowed is True
    denied = service.check(request)

    assert denied.allowed is False
    assert denied.reason_code == "rate_limited"
    assert denied.limiting_dimension == dimension
    assert "203.0.113.10" not in str(denied.to_dict())


def test_service_evaluates_deterministic_priority_order():
    lower = rule(rule_key="b_low", dimension="credential", capacity=1, refill_tokens=1, priority=20)
    higher = rule(rule_key="a_high", dimension="workspace", capacity=1, refill_tokens=1, priority=10)
    request = rate_request(policy_profile=policy_with_rules(lower, higher))
    service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET)

    service.check(request)
    denied = service.check(request)

    assert denied.rule_key == "a_high"


def test_service_missing_required_identity_fails_safely():
    request = rate_request(client_ip_identity=None, policy_profile=policy_with_rules(rule(dimension="ip")))
    service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET)

    denied = service.check(request)

    assert denied.allowed is False
    assert denied.reason_code == "rate_limited"


class FailingStore:
    def __init__(self, exc):
        self.exc = exc

    def consume(self, **_kwargs):
        raise self.exc

    def health_check(self):
        return False


@pytest.mark.parametrize("category", ["widget_message_send", "widget_session_create", "partner_api_request"])
def test_redis_failure_fails_closed_for_sensitive_categories(category):
    sensitive_rule = rule(category=category, fail_mode="fail_closed")
    request = rate_request(category=category, policy_profile=policy_with_rules(sensitive_rule))
    service = RateLimitService(store=FailingStore(RateLimitStoreError("down")), identity_secret=SECRET)

    decision = service.check(request)

    assert decision.allowed is False
    assert decision.reason_code == "temporarily_unavailable"


def test_redis_timeout_emits_timeout_event():
    events = InMemoryAccessEventSink()
    service = RateLimitService(store=FailingStore(RateLimitStoreTimeout("slow")), identity_secret=SECRET, event_sink=events)

    decision = service.check(rate_request())

    assert decision.allowed is False
    assert events.events[-1].event_type == "rate_limit.redis_timeout"


def test_widget_config_uses_local_fallback_when_enabled_and_exhausts():
    config_rule = rule(category="widget_config_read", dimension="credential", capacity=2, refill_tokens=2, fail_mode="constrained_fail_open")
    request = rate_request(category="widget_config_read", policy_profile=policy_with_rules(config_rule))
    service = RateLimitService(
        store=FailingStore(RateLimitStoreError("down")),
        identity_secret=SECRET,
        local_fallback=LocalFallbackLimiter(enabled=True),
    )

    assert service.check(request).allowed is True
    assert service.check(request).allowed is True
    denied = service.check(request)

    assert denied.allowed is False
    assert denied.degraded is True


def test_local_fallback_disabled_does_not_fail_open():
    config_rule = rule(category="widget_config_read", dimension="credential", fail_mode="constrained_fail_open")
    request = rate_request(category="widget_config_read", policy_profile=policy_with_rules(config_rule))
    service = RateLimitService(store=FailingStore(RateLimitStoreError("down")), identity_secret=SECRET, local_fallback=LocalFallbackLimiter(enabled=False))

    assert service.check(request).allowed is False


def test_emergency_controls_deny_before_store():
    service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET, emergency_controls=EmergencyControls(deny_all=True))

    decision = service.check(rate_request())

    assert decision.allowed is False
    assert decision.reason_code == "temporarily_unavailable"


def credential_record(policy_profile="widget"):
    return CredentialRecord(
        credential_id="cred-1",
        organisation_id="org-1",
        workspace_id="workspace-1",
        credential_type="widget_public_key",
        public_identifier="public-test",
        status="active",
        environment="production",
        capabilities=("widget_chat",),
        policy_profile=policy_profile,
        created_at=NOW,
    )


def origin_service(events):
    return OriginValidationService(
        origin_lookup=lambda _credential_id, _environment: [AllowedOriginRecord("origin-1", "cred-1", "https", "example.com", None, False, "production", True)],
        event_sink=events,
    )


def make_gateway(rate_service=None, origin=None, record=None):
    policy_registry = default_policy_registry()
    tenant_service = PublicTenantResolutionService(
        credential_registry=InMemoryCredentialRegistry([record or credential_record()]),
        policy_registry=policy_registry,
        checks=TenantResolutionChecks(
            organisation_is_active=lambda _org: True,
            workspace_is_active=lambda _workspace: True,
            workspace_belongs_to_organisation=lambda _workspace, _org: True,
        ),
    )
    events = InMemoryAccessEventSink()
    gateway = PublicAccessGateway(
        channel_registry=ChannelRegistry([DevelopmentTestChannelAdapter()]),
        tenant_resolution_service=tenant_service,
        policy_registry=policy_registry,
        event_sink=events,
        origin_validation_service=origin if origin is not None else origin_service(events),
        rate_limit_service=rate_service,
    )
    return gateway, events


def raw_gateway_request(**overrides):
    request = {
        "request_id": "req-1",
        "channel": "internal_test",
        "credential_type": "widget_public_key",
        "public_identifier": "public-test",
        "origin": "https://example.com",
        "client_ip": "203.0.113.10",
        "rate_limit_category": "widget_message_send",
        "message": "Hello",
    }
    request.update(overrides)
    return request


def test_gateway_invokes_rate_limit_after_origin_validation():
    events = InMemoryAccessEventSink()
    rate_service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET, event_sink=events)
    gateway, gateway_events = make_gateway(rate_service=rate_service, origin=origin_service(events))

    response = gateway.validate(raw_gateway_request())
    event_types = [event.event_type for event in events.events + gateway_events.events]

    assert response.status == "validated"
    assert "origin.validation.allowed" in event_types
    assert "rate_limit.allowed" in event_types


def test_gateway_origin_denial_prevents_rate_limit_consumption():
    rate_events = InMemoryAccessEventSink()
    rate_service = RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET, event_sink=rate_events)
    gateway, _events = make_gateway(rate_service=rate_service)

    response = gateway.validate(raw_gateway_request(origin="https://evil.example"))

    assert response.status == "rejected"
    assert response.safe_error is not None and response.safe_error.code == "origin_not_allowed"
    assert rate_events.events == []


def test_gateway_rate_denial_returns_safe_retryable_error_and_no_public_route():
    limited_rule = rule(capacity=0 + 1, refill_tokens=1)
    request_policy = policy_with_rules(limited_rule)
    record = credential_record(policy_profile="unit_policy")
    policy_registry = default_policy_registry()
    policy_registry.register(request_policy)
    tenant_service = PublicTenantResolutionService(
        credential_registry=InMemoryCredentialRegistry([record]),
        policy_registry=policy_registry,
        checks=TenantResolutionChecks(lambda _org: True, lambda _workspace: True, lambda _workspace, _org: True),
    )
    events = InMemoryAccessEventSink()
    gateway = PublicAccessGateway(
        channel_registry=ChannelRegistry([DevelopmentTestChannelAdapter()]),
        tenant_resolution_service=tenant_service,
        policy_registry=policy_registry,
        event_sink=events,
        origin_validation_service=origin_service(events),
        rate_limit_service=RateLimitService(store=InMemoryRateLimitStore(), identity_secret=SECRET, event_sink=events),
    )

    assert gateway.validate(raw_gateway_request()).status == "validated"
    response = gateway.validate(raw_gateway_request())

    assert response.status == "rejected"
    assert response.safe_error is not None
    assert response.safe_error.code == "rate_limited"
    assert response.safe_error.retry_after_seconds is not None
    assert response.payload == {}

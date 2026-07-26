from __future__ import annotations

from types import SimpleNamespace

from fastapi import Request

from app.operations.logging import redact
from app.operations.telemetry import TelemetryConfig, normalise_route, safe_attributes, validate_telemetry_config


def test_route_normalisation_uses_templates_for_public_widget_keys() -> None:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/widget/wpk_live_abc123/messages",
        "headers": [],
        "route": SimpleNamespace(path="/api/v1/widget/{public_key}/messages"),
    }
    request = Request(scope)

    assert normalise_route(request) == "/api/v1/widget/{public_key}/messages"


def test_safe_telemetry_attributes_are_allowlisted_and_redacted() -> None:
    attributes = safe_attributes(
        {
            "http.route": "/api/v1/widget/wpk_live_abc123/messages",
            "request.id": "req-123",
            "message": "customer question",
            "answer": "assistant answer",
            "authorization": "Bearer secret",
            "session_token": "pss_dev_abcdefghijklmnop.abcdefghijklmnopqrstuvwx",
            "error.category": "safe_internal_error",
            "tenant_id": "tenant-raw",
        }
    )

    rendered = str(attributes)
    assert "customer question" not in rendered
    assert "assistant answer" not in rendered
    assert "Bearer secret" not in rendered
    assert "pss_dev_" not in rendered
    assert "tenant-raw" not in rendered
    assert attributes["request.id"] == "req-123"
    assert attributes["error.category"] == "safe_internal_error"


def test_redaction_covers_preview_grants_drafts_and_provider_secrets() -> None:
    rendered = str(
        redact(
            {
                "preview_grant": "wpg_sensitive_preview",
                "draft_configuration": {"welcome_message": "draft internal copy"},
                "provider_prompt": "system prompt",
                "connection_string": "InstrumentationKey=secret;IngestionEndpoint=https://example",
                "database_url": "postgres://user:pass@example/db",
            }
        )
    )

    assert "wpg_sensitive_preview" not in rendered
    assert "draft internal copy" not in rendered
    assert "system prompt" not in rendered
    assert "InstrumentationKey" not in rendered
    assert "postgres://user" not in rendered


def test_telemetry_config_validation_requires_release_identity_when_enabled() -> None:
    failures = validate_telemetry_config(
        TelemetryConfig(
            enabled=True,
            connection_string_present=False,
            environment="pilot",
            service_name="chatbotweb-api",
            release_version="bootstrap-placeholder",
            sampling_ratio=1.0,
        )
    )

    assert any("release version" in failure for failure in failures)

from dataclasses import dataclass, field
from typing import Any

from app.access.channels.base import ChannelCapabilities, PublicChannelAdapter
from app.access.contracts import PublicCredentialReference, validate_metadata
from app.access.errors import PublicAccessErrorDetail, raise_public_error

FORBIDDEN_PUBLIC_WIDGET_FIELDS = {
    "organisation_id",
    "organization_id",
    "workspace_id",
    "credential_id",
    "conversation_id",
    "session_id",
    "message",
    "email",
    "phone",
    "user",
    "user_id",
    "identity",
    "origin",
    "ip",
    "ip_address",
    "client_ip",
    "model_key",
    "provider_key",
    "prompt_key",
    "policy_profile",
    "timeout",
    "limit",
    "max_messages",
}

DASHBOARD_PUBLIC_FORBIDDEN_HEADERS = {
    "authorization",
    "x-development-user-email",
    "x-development-role",
}


@dataclass
class WidgetChannelAdapter(PublicChannelAdapter):
    channel_key: str = "widget"
    display_name: str = "Public Website Widget"
    capabilities: ChannelCapabilities = field(default_factory=lambda: ChannelCapabilities(supports_sessions=True, supports_markdown=True))
    default_policy_profile: str = "widget"

    def parse_request(self, raw_request: dict[str, Any]) -> dict[str, Any]:
        return dict(raw_request)

    def extract_public_credential(self, parsed_request: dict[str, Any]) -> PublicCredentialReference:
        public_key = str(parsed_request.get("public_key") or "").strip()
        if not public_key:
            raise_public_error("invalid_widget")
        return PublicCredentialReference(credential_type="widget_public_key", public_identifier=public_key)

    def extract_origin(self, parsed_request: dict[str, Any]) -> str | None:
        origin = parsed_request.get("origin")
        return str(origin).strip() if origin else None

    def extract_session_token(self, parsed_request: dict[str, Any]) -> str | None:
        return None

    def validate_request_shape(self, parsed_request: dict[str, Any]) -> None:
        headers = parsed_request.get("headers", {})
        if isinstance(headers, dict):
            lowered = {str(key).lower() for key in headers}
            if DASHBOARD_PUBLIC_FORBIDDEN_HEADERS.intersection(lowered):
                raise_public_error("invalid_request")
        body = parsed_request.get("body") or {}
        if not isinstance(body, dict):
            raise_public_error("invalid_request")
        forbidden = FORBIDDEN_PUBLIC_WIDGET_FIELDS.intersection({str(key) for key in body})
        if forbidden:
            raise_public_error("invalid_request")
        metadata = body.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise_public_error("invalid_request")
        try:
            validate_metadata(metadata)
        except ValueError:
            raise_public_error("invalid_request")
        client_request_id = body.get("client_request_id")
        if client_request_id is not None and (not isinstance(client_request_id, str) or len(client_request_id) > 120):
            raise_public_error("invalid_request")
        requested_language = body.get("requested_language")
        if requested_language is not None and (not isinstance(requested_language, str) or len(requested_language) > 16):
            raise_public_error("invalid_request")

    def normalise_message(self, parsed_request: dict[str, Any]) -> str:
        return ""

    def format_response(self, response):
        payload = dict(response.payload)
        capabilities = payload.get("capabilities") or {}
        return {
            "session_token": payload.get("public_session_token"),
            "expires_at": payload.get("expires_at"),
            "absolute_expires_at": payload.get("absolute_expires_at"),
            "inactivity_timeout_seconds": payload.get("inactivity_timeout_seconds"),
            "max_messages": payload.get("max_messages"),
            "remaining_messages": payload.get("remaining_messages", payload.get("max_messages")),
            "configuration_version": payload.get("configuration_version"),
            "capabilities": capabilities,
            "request_id": response.request_id,
        }

    def format_error(self, error: PublicAccessErrorDetail) -> dict[str, Any]:
        return {"error": error.to_public_dict()}
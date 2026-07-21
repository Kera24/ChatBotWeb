from __future__ import annotations

import re
from typing import Any

from app.access.errors import raise_public_error
from app.core.config import settings

FORBIDDEN_PUBLIC_MESSAGE_FIELDS = {
    "organisation_id",
    "organization_id",
    "workspace_id",
    "credential_id",
    "conversation_id",
    "session_id",
    "public_session_id",
    "model_key",
    "provider_key",
    "prompt_key",
    "retrieval_limit",
    "context_size",
    "context_limit",
    "output_token_limit",
    "max_output_tokens",
    "system_instructions",
    "conversation_history",
    "email",
    "phone",
    "identity",
    "user_id",
    "origin",
    "ip",
    "ip_address",
    "policy_profile",
    "tool",
    "tools",
    "capabilities",
}

_ALLOWED_CONTROL_CHARS = {"\n", "\t"}
_BASE64ISH = re.compile(r"^[A-Za-z0-9+/=_-]{256,}$")


def validate_public_message_payload(payload: dict[str, Any]) -> tuple[str, dict[str, str | int | float | bool | None]]:
    if not isinstance(payload, dict):
        raise_public_error("invalid_request")
    forbidden = FORBIDDEN_PUBLIC_MESSAGE_FIELDS.intersection({str(key) for key in payload})
    if forbidden:
        raise_public_error("invalid_request")
    message = payload.get("message")
    if not isinstance(message, str):
        raise_public_error("invalid_message")
    canonical = normalise_message(message)
    metadata = validate_message_metadata(payload.get("metadata") or {})
    return canonical, metadata


def normalise_message(message: str) -> str:
    canonical = message.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not canonical:
        raise_public_error("invalid_message")
    if "\x00" in canonical:
        raise_public_error("invalid_message")
    if len(canonical) > settings.PUBLIC_MESSAGE_MAX_CHARACTERS:
        raise_public_error("message_too_large")
    if len(canonical.encode("utf-8")) > settings.PUBLIC_MESSAGE_MAX_BYTES:
        raise_public_error("message_too_large")
    unsafe_controls = [char for char in canonical if ord(char) < 32 and char not in _ALLOWED_CONTROL_CHARS]
    if len(unsafe_controls) > 0:
        raise_public_error("invalid_message")
    if _looks_binary_or_encoded(canonical):
        raise_public_error("invalid_message")
    return canonical


def validate_message_metadata(metadata: Any) -> dict[str, str | int | float | bool | None]:
    if not isinstance(metadata, dict):
        raise_public_error("invalid_request")
    if len(metadata) > settings.PUBLIC_MESSAGE_METADATA_MAX_ITEMS:
        raise_public_error("invalid_request")
    safe: dict[str, str | int | float | bool | None] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not key or len(key) > settings.PUBLIC_MESSAGE_METADATA_KEY_MAX_LENGTH:
            raise_public_error("invalid_request")
        if key in FORBIDDEN_PUBLIC_MESSAGE_FIELDS:
            raise_public_error("invalid_request")
        if isinstance(value, str):
            if len(value) > settings.PUBLIC_MESSAGE_METADATA_VALUE_MAX_LENGTH:
                raise_public_error("invalid_request")
            if "\x00" in value:
                raise_public_error("invalid_request")
            safe[key] = value
        elif value is None or isinstance(value, (int, float, bool)):
            safe[key] = value
        else:
            raise_public_error("invalid_request")
    return safe


def _looks_binary_or_encoded(value: str) -> bool:
    compact = "".join(value.split())
    return bool(_BASE64ISH.fullmatch(compact))

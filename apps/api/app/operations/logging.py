from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_FIELD_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "session_token",
    "token",
    "authorization_header",
    "api_key",
    "provider_key",
    "database_url",
    "message",
    "answer",
    "quoted_text",
    "prompt",
    "retrieved_context",
}

_PUBLIC_KEY_PATTERN = re.compile(r"wpk_[A-Za-z0-9_-]+")
_SESSION_TOKEN_PATTERN = re.compile(r"pss_[A-Za-z0-9_.-]+")


def pseudonymous_identifier(value: str, *, prefix: str = "id") -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SENSITIVE_FIELD_NAMES or "secret" in lowered or "password" in lowered:
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        redacted = _SESSION_TOKEN_PATTERN.sub("[redacted-session-token]", value)
        redacted = _PUBLIC_KEY_PATTERN.sub(lambda match: pseudonymous_identifier(match.group(0), prefix="widget"), redacted)
        return redacted[:512]
    return value


def log_operational_event(logger: logging.Logger, event: Mapping[str, Any]) -> None:
    logger.info(json.dumps(redact(dict(event)), sort_keys=True, separators=(",", ":")))


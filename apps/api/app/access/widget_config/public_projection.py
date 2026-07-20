from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from urllib.parse import urljoin, urlparse

from app.access.widget_config.validation import (
    MAX_SUGGESTIONS,
    validate_colour,
    validate_language,
    validate_max_initial_suggestions,
    validate_optional_colour,
    validate_optional_text,
    validate_position,
    validate_suggestions,
    validate_theme_mode,
    validate_url,
    validate_widget_text,
)
from app.db.models import WidgetConfiguration

PUBLIC_WIDGET_CONFIG_SCHEMA_VERSION = "1.0"
_ALLOWED_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def project_public_widget_configuration(
    configuration: WidgetConfiguration,
    *,
    request_id: str,
    asset_base_url: str | None = None,
) -> tuple[dict[str, object], bool]:
    suggestions = validate_suggestions(list(configuration.suggested_questions_json or []))[:MAX_SUGGESTIONS]
    max_initial_suggestions = validate_max_initial_suggestions(
        int(configuration.max_initial_suggestions or 0),
        suggestion_count=len(suggestions),
    )
    logo_url, logo_omitted = project_asset_url(configuration.logo_path, asset_base_url=asset_base_url)
    avatar_url, avatar_omitted = project_asset_url(configuration.avatar_path, asset_base_url=asset_base_url)
    show_citations = bool(configuration.show_citations)
    allow_history = bool(configuration.allow_conversation_history)
    payload: dict[str, object] = {
        "widget": {
            "bot_name": validate_widget_text(configuration.bot_name, field_name="bot_name", max_length=120),
            "welcome_message": validate_widget_text(configuration.welcome_message, field_name="welcome_message", max_length=500),
            "launcher_label": validate_widget_text(configuration.launcher_label, field_name="launcher_label", max_length=80),
            "primary_colour": validate_colour(configuration.primary_colour, field_name="primary_colour"),
            "secondary_colour": validate_optional_colour(configuration.secondary_colour, field_name="secondary_colour"),
            "logo_url": logo_url,
            "avatar_url": avatar_url,
            "position": validate_position(configuration.position),
            "theme_mode": validate_theme_mode(configuration.theme_mode),
            "language": validate_language(configuration.language),
        },
        "behaviour": {
            "suggested_questions": suggestions,
            "max_initial_suggestions": max_initial_suggestions,
            "show_citations": show_citations,
            "allow_conversation_history": allow_history,
            "session_required": True,
            "messages_enabled": True,
        },
        "privacy": {
            "privacy_notice_text": validate_optional_text(configuration.privacy_notice_text, field_name="privacy_notice_text", max_length=1000),
            "privacy_notice_url": validate_url(configuration.privacy_notice_url, field_name="privacy_notice_url"),
            "terms_url": validate_url(configuration.terms_url, field_name="terms_url"),
            "fallback_contact_text": validate_optional_text(configuration.fallback_contact_text, field_name="fallback_contact_text", max_length=500),
        },
        "capabilities": {
            "can_create_session": True,
            "can_send_messages": True,
            "citations_enabled": show_citations,
            "conversation_history_enabled": allow_history,
        },
        "configuration_version": int(configuration.configuration_version),
        "response_schema_version": PUBLIC_WIDGET_CONFIG_SCHEMA_VERSION,
        "published_at": configuration.published_at.isoformat() if configuration.published_at else "",
        "request_id": request_id,
    }
    return payload, bool(logo_omitted or avatar_omitted)


def project_asset_url(value: str | None, *, asset_base_url: str | None = None) -> tuple[str | None, bool]:
    if value is None or not value.strip():
        return None, False
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.netloc:
            return None, True
        return (candidate, False) if _has_allowed_asset_extension(parsed.path) else (None, True)
    if not asset_base_url or not asset_base_url.strip():
        return None, True
    if "\\" in candidate or ".." in candidate or candidate.startswith(("/", "~")):
        return None, True
    base = asset_base_url.strip().rstrip("/") + "/"
    base_parsed = urlparse(base)
    if base_parsed.scheme != "https" or not base_parsed.netloc or base_parsed.username or base_parsed.password:
        return None, True
    if not _has_allowed_asset_extension(candidate):
        return None, True
    return urljoin(base, candidate), False


def public_widget_config_etag(public_projection: dict[str, object], *, cache_key: str | None = None) -> str:
    stable = deepcopy(public_projection)
    stable.pop("request_id", None)
    if cache_key is not None:
        stable["_cache_key"] = cache_key
    canonical = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def _has_allowed_asset_extension(path: str) -> bool:
    lowered = path.lower().split("?", 1)[0].split("#", 1)[0]
    return any(lowered.endswith(extension) for extension in _ALLOWED_ASSET_EXTENSIONS)
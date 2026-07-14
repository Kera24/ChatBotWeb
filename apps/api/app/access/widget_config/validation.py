from __future__ import annotations

import re
from urllib.parse import urlparse

HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
VALID_POSITIONS = {"bottom_right", "bottom_left"}
VALID_THEME_MODES = {"light", "dark", "system"}
VALID_LANGUAGES = {"en", "en-AU", "en-US", "en-GB"}
MAX_SUGGESTIONS = 6


class WidgetValidationError(ValueError):
    pass


def validate_widget_text(value: str, *, field_name: str, min_length: int = 1, max_length: int) -> str:
    safe = value.strip()
    if len(safe) < min_length or len(safe) > max_length:
        raise WidgetValidationError(f"{field_name} length is not valid.")
    if contains_html(safe):
        raise WidgetValidationError(f"{field_name} must be plain text.")
    return safe


def validate_optional_text(value: str | None, *, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    safe = value.strip()
    if not safe:
        return None
    return validate_widget_text(safe, field_name=field_name, max_length=max_length)


def validate_colour(value: str, *, field_name: str) -> str:
    safe = value.strip()
    if not HEX_COLOUR.fullmatch(safe):
        raise WidgetValidationError(f"{field_name} must be a safe hex colour.")
    if not _has_safe_text_contrast(safe):
        raise WidgetValidationError(f"{field_name} does not provide a safe text contrast approximation.")
    return safe.lower()


def validate_optional_colour(value: str | None, *, field_name: str) -> str | None:
    if value is None or not value.strip():
        return None
    return validate_colour(value, field_name=field_name)


def validate_suggestions(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    if len(values) > MAX_SUGGESTIONS:
        raise WidgetValidationError("Too many suggested questions.")
    return [validate_widget_text(item, field_name="suggested question", max_length=160) for item in values]


def validate_url(value: str | None, *, field_name: str) -> str | None:
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise WidgetValidationError(f"{field_name} must be a safe HTTPS URL.")
    if contains_html(value):
        raise WidgetValidationError(f"{field_name} is not safe.")
    return value.strip()


def validate_asset_path(value: str | None, *, field_name: str) -> str | None:
    if value is None or not value.strip():
        return None
    safe = value.strip()
    parsed = urlparse(safe)
    if parsed.scheme and parsed.scheme not in {"https"}:
        raise WidgetValidationError(f"{field_name} must use a safe asset path or HTTPS URL.")
    if contains_html(safe) or ".." in safe or len(safe) > 512:
        raise WidgetValidationError(f"{field_name} is not safe.")
    return safe


def validate_position(value: str) -> str:
    if value not in VALID_POSITIONS:
        raise WidgetValidationError("Widget position is not supported.")
    return value


def validate_theme_mode(value: str) -> str:
    if value not in VALID_THEME_MODES:
        raise WidgetValidationError("Widget theme mode is not supported.")
    return value


def validate_language(value: str) -> str:
    if value not in VALID_LANGUAGES:
        raise WidgetValidationError("Widget language is not supported.")
    return value


def validate_max_initial_suggestions(value: int, *, suggestion_count: int) -> int:
    if value < 0 or value > MAX_SUGGESTIONS or value > suggestion_count:
        raise WidgetValidationError("max_initial_suggestions is outside allowed bounds.")
    return value


def contains_html(value: str) -> bool:
    return bool(re.search(r"<\s*/?\s*[a-zA-Z!]|<|>|javascript:", value, flags=re.IGNORECASE))


def _has_safe_text_contrast(hex_colour: str) -> bool:
    r = int(hex_colour[1:3], 16) / 255
    g = int(hex_colour[3:5], 16) / 255
    b = int(hex_colour[5:7], 16) / 255
    luminance = 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)
    contrast_with_black = (luminance + 0.05) / 0.05
    contrast_with_white = 1.05 / (luminance + 0.05)
    return max(contrast_with_black, contrast_with_white) >= 4.5


def _linear(value: float) -> float:
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4

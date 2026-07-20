from __future__ import annotations

from dataclasses import dataclass

from app.access.errors import PublicAccessErrorDetail, error_detail
from app.core.config import settings


@dataclass(frozen=True)
class WidgetOperationalControls:
    public_widgets_enabled: bool = True
    public_widget_messages_enabled: bool = True
    pilot_enforcement_enabled: bool = False
    pilot_allowlist: frozenset[str] = frozenset()
    disabled_widgets: frozenset[str] = frozenset()


def parse_bool(value: str | bool | None, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalised = value.strip().lower()
    if normalised in {"1", "true", "yes", "on"}:
        return True
    if normalised in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def parse_identifier_list(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    identifiers = [item.strip() for item in value.split(",") if item.strip()]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate widget operational identifier.")
    for identifier in identifiers:
        if len(identifier) > 160 or any(ch.isspace() for ch in identifier):
            raise ValueError("Invalid widget operational identifier.")
    return frozenset(identifiers)


def controls_from_settings() -> WidgetOperationalControls:
    return WidgetOperationalControls(
        public_widgets_enabled=parse_bool(settings.PUBLIC_WIDGETS_ENABLED, default=True),
        public_widget_messages_enabled=parse_bool(settings.PUBLIC_WIDGET_MESSAGES_ENABLED, default=True),
        pilot_enforcement_enabled=parse_bool(settings.PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED, default=False),
        pilot_allowlist=parse_identifier_list(settings.PUBLIC_WIDGET_PILOT_ALLOWLIST),
        disabled_widgets=parse_identifier_list(settings.PUBLIC_WIDGET_DISABLED_WIDGETS),
    )


def resolve_controls(app_state: object | None = None) -> WidgetOperationalControls:
    override = getattr(app_state, "widget_operational_controls", None) if app_state is not None else None
    if isinstance(override, WidgetOperationalControls):
        return override
    return controls_from_settings()


def evaluate_widget_access(public_key: str, *, controls: WidgetOperationalControls, operation: str) -> PublicAccessErrorDetail | None:
    if not controls.public_widgets_enabled:
        return error_detail("temporarily_unavailable")
    if public_key in controls.disabled_widgets:
        return error_detail("invalid_widget")
    if controls.pilot_enforcement_enabled and public_key not in controls.pilot_allowlist:
        return error_detail("invalid_widget")
    if operation == "message" and not controls.public_widget_messages_enabled:
        return error_detail("temporarily_unavailable")
    return None


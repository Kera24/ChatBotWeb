from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.access.credentials.service import CredentialNotFound, get_credential
from app.access.widget_config.repository import create_configuration_record, get_configuration_for_credential
from app.access.widget_config.validation import (
    WidgetValidationError,
    validate_asset_path,
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
from app.repositories.audit_repository import add_audit_event


class WidgetConfigurationNotFound(LookupError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_widget_payload(*, bot_name: str = "Assistant") -> dict:
    return {
        "bot_name": bot_name,
        "welcome_message": "How can I help?",
        "launcher_label": "Chat",
        "primary_colour": "#111827",
        "secondary_colour": None,
        "logo_path": None,
        "avatar_path": None,
        "position": "bottom_right",
        "theme_mode": "system",
        "suggested_questions_json": [],
        "fallback_contact_text": None,
        "privacy_notice_text": None,
        "privacy_notice_url": None,
        "terms_url": None,
        "language": "en",
        "show_citations": True,
        "allow_conversation_history": True,
        "max_initial_suggestions": 0,
    }


def validate_configuration_payload(payload: dict, *, partial: bool = False, existing: WidgetConfiguration | None = None) -> dict:
    base = {}
    if existing is not None:
        base = {
            "bot_name": existing.bot_name,
            "welcome_message": existing.welcome_message,
            "launcher_label": existing.launcher_label,
            "primary_colour": existing.primary_colour,
            "secondary_colour": existing.secondary_colour,
            "logo_path": existing.logo_path,
            "avatar_path": existing.avatar_path,
            "position": existing.position,
            "theme_mode": existing.theme_mode,
            "suggested_questions_json": list(existing.suggested_questions_json or []),
            "fallback_contact_text": existing.fallback_contact_text,
            "privacy_notice_text": existing.privacy_notice_text,
            "privacy_notice_url": existing.privacy_notice_url,
            "terms_url": existing.terms_url,
            "language": existing.language,
            "show_citations": existing.show_citations,
            "allow_conversation_history": existing.allow_conversation_history,
            "max_initial_suggestions": existing.max_initial_suggestions,
        }
    elif partial:
        base = default_widget_payload()
    merged = {**base, **payload}
    required = default_widget_payload().keys()
    missing = [key for key in required if key not in merged]
    if missing:
        raise WidgetValidationError("Widget configuration is missing required fields.")
    suggestions = validate_suggestions(merged.get("suggested_questions_json"))
    return {
        "bot_name": validate_widget_text(merged["bot_name"], field_name="bot_name", max_length=120),
        "welcome_message": validate_widget_text(merged["welcome_message"], field_name="welcome_message", max_length=500),
        "launcher_label": validate_widget_text(merged["launcher_label"], field_name="launcher_label", max_length=80),
        "primary_colour": validate_colour(merged["primary_colour"], field_name="primary_colour"),
        "secondary_colour": validate_optional_colour(merged.get("secondary_colour"), field_name="secondary_colour"),
        "logo_path": validate_asset_path(merged.get("logo_path"), field_name="logo_path"),
        "avatar_path": validate_asset_path(merged.get("avatar_path"), field_name="avatar_path"),
        "position": validate_position(merged["position"]),
        "theme_mode": validate_theme_mode(merged["theme_mode"]),
        "suggested_questions_json": suggestions,
        "fallback_contact_text": validate_optional_text(merged.get("fallback_contact_text"), field_name="fallback_contact_text", max_length=500),
        "privacy_notice_text": validate_optional_text(merged.get("privacy_notice_text"), field_name="privacy_notice_text", max_length=1000),
        "privacy_notice_url": validate_url(merged.get("privacy_notice_url"), field_name="privacy_notice_url"),
        "terms_url": validate_url(merged.get("terms_url"), field_name="terms_url"),
        "language": validate_language(merged["language"]),
        "show_citations": bool(merged["show_citations"]),
        "allow_conversation_history": bool(merged["allow_conversation_history"]),
        "max_initial_suggestions": validate_max_initial_suggestions(int(merged["max_initial_suggestions"]), suggestion_count=len(suggestions)),
    }


def create_default_configuration(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, actor_user_id: str | None, bot_name: str = "Assistant") -> WidgetConfiguration:
    get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    existing = get_configuration_for_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if existing is not None:
        raise WidgetValidationError("Widget configuration already exists for this credential.")
    values = validate_configuration_payload(default_widget_payload(bot_name=bot_name))
    configuration = WidgetConfiguration(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        credential_id=credential_id,
        status="draft",
        configuration_version=0,
        **values,
    )
    create_configuration_record(db, configuration)
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="widget_configuration.created",
        entity_type="widget_configuration",
        entity_id=configuration.id,
        new_status="draft",
        metadata_json={"credential_id": credential_id},
    )
    db.commit()
    db.refresh(configuration)
    return configuration


def get_configuration(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> WidgetConfiguration:
    get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    configuration = get_configuration_for_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if configuration is None:
        raise WidgetConfigurationNotFound("Widget configuration not found for credential.")
    return configuration


def upsert_draft_configuration(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, actor_user_id: str | None, payload: dict) -> WidgetConfiguration:
    get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    configuration = get_configuration_for_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    if configuration is None:
        values = validate_configuration_payload({**default_widget_payload(), **payload})
        configuration = WidgetConfiguration(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
            status="draft",
            configuration_version=0,
            **values,
        )
        create_configuration_record(db, configuration)
        action = "widget_configuration.created"
    else:
        values = validate_configuration_payload(payload, partial=True, existing=configuration)
        for key, value in values.items():
            setattr(configuration, key, value)
        if configuration.status == "published":
            configuration.status = "draft"
        action = "widget_configuration.updated"
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="widget_configuration",
        entity_id=configuration.id,
        new_status=configuration.status,
        metadata_json={"credential_id": credential_id},
    )
    db.commit()
    db.refresh(configuration)
    return configuration


def publish_configuration(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, actor_user_id: str | None) -> WidgetConfiguration:
    configuration = get_configuration(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    previous_status = configuration.status
    configuration.status = "published"
    configuration.configuration_version += 1
    configuration.published_at = utc_now()
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="widget_configuration.published",
        entity_type="widget_configuration",
        entity_id=configuration.id,
        previous_status=previous_status,
        new_status="published",
        metadata_json={"credential_id": credential_id, "configuration_version": configuration.configuration_version},
    )
    db.commit()
    db.refresh(configuration)
    return configuration


def safe_public_configuration(configuration: WidgetConfiguration) -> dict[str, object]:
    return {
        "bot_name": configuration.bot_name,
        "welcome_message": configuration.welcome_message,
        "launcher_label": configuration.launcher_label,
        "primary_colour": configuration.primary_colour,
        "secondary_colour": configuration.secondary_colour,
        "logo_path": configuration.logo_path,
        "avatar_path": configuration.avatar_path,
        "position": configuration.position,
        "theme_mode": configuration.theme_mode,
        "suggested_questions": configuration.suggested_questions_json or [],
        "fallback_contact_text": configuration.fallback_contact_text,
        "privacy_notice_text": configuration.privacy_notice_text,
        "privacy_notice_url": configuration.privacy_notice_url,
        "terms_url": configuration.terms_url,
        "language": configuration.language,
        "show_citations": configuration.show_citations,
        "allow_conversation_history": configuration.allow_conversation_history,
        "max_initial_suggestions": configuration.max_initial_suggestions,
        "configuration_version": configuration.configuration_version,
    }

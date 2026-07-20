from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access.credentials.service import CredentialValidationError, create_credential, get_credential
from app.access.origin_validation.repository import list_active_origins_for_credential
from app.access.widget_config.service import default_widget_payload, validate_configuration_payload
from app.access.widget_config.validation import WidgetValidationError
from app.db.models import Widget, WidgetConfigurationRevision
from app.repositories.audit_repository import add_audit_event

CONFIG_FIELDS = (
    "bot_name",
    "welcome_message",
    "launcher_label",
    "primary_colour",
    "secondary_colour",
    "logo_path",
    "avatar_path",
    "position",
    "theme_mode",
    "suggested_questions_json",
    "fallback_contact_text",
    "privacy_notice_text",
    "privacy_notice_url",
    "terms_url",
    "language",
    "show_citations",
    "allow_conversation_history",
    "max_initial_suggestions",
)


class WidgetAdminNotFound(LookupError):
    pass


class WidgetAdminConflict(ValueError):
    pass


@dataclass(frozen=True)
class WidgetAdminFieldError:
    field: str
    code: str
    message: str


class WidgetAdminValidationError(ValueError):
    def __init__(self, message: str, *, errors: list[WidgetAdminFieldError] | None = None):
        super().__init__(message)
        self.errors = errors or []


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def list_widgets(db: Session, *, organisation_id: str, workspace_id: str) -> list[Widget]:
    statement = (
        select(Widget)
        .where(Widget.organisation_id == organisation_id, Widget.workspace_id == workspace_id, Widget.archived_at.is_(None))
        .order_by(Widget.created_at.desc(), Widget.id.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_widget(db: Session, *, organisation_id: str, workspace_id: str, widget_id: str) -> Widget:
    widget = db.execute(
        select(Widget).where(
            Widget.id == widget_id,
            Widget.organisation_id == organisation_id,
            Widget.workspace_id == workspace_id,
            Widget.archived_at.is_(None),
        )
    ).scalar_one_or_none()
    if widget is None:
        raise WidgetAdminNotFound("Widget not found.")
    return widget


def create_widget(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    display_name: str,
    environment: str,
    actor_user_id: str | None,
    initial_configuration: dict[str, Any] | None = None,
) -> Widget:
    safe_name = display_name.strip()
    if not safe_name or len(safe_name) > 160 or _contains_html(safe_name):
        raise WidgetAdminValidationError("Widget display name is not valid.", errors=[WidgetAdminFieldError("display_name", "invalid", "Display name is not valid.")])
    try:
        credential = create_credential(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_type="widget_public_key",
            display_name=safe_name,
            environment=environment,
            policy_profile="widget",
            capabilities=["widget_config", "widget_chat"],
            created_by_user_id=actor_user_id,
        )
    except CredentialValidationError as exc:
        raise WidgetAdminValidationError(str(exc), errors=[WidgetAdminFieldError("environment", "invalid", str(exc))]) from exc

    values = validate_configuration_payload({**default_widget_payload(bot_name=safe_name), **(initial_configuration or {})})
    widget = Widget(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        public_credential_id=credential.id,
        display_name=safe_name,
        operational_status="enabled",
        pilot_status="not_approved",
        release_channel="pilot",
    )
    db.add(widget)
    db.flush()
    draft = WidgetConfigurationRevision(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        widget_id=widget.id,
        public_credential_id=credential.id,
        revision_number=1,
        status="draft",
        concurrency_version=1,
        created_by_user_id=actor_user_id,
        configuration_hash=_configuration_hash(values),
        **values,
    )
    db.add(draft)
    db.flush()
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="widget.created",
        entity_type="widget",
        entity_id=widget.id,
        new_status=widget.operational_status,
        metadata_json={"draft_revision_id": draft.id, "public_credential_id": credential.id},
    )
    db.commit()
    db.refresh(widget)
    return widget


def get_current_draft(db: Session, *, widget: Widget) -> WidgetConfigurationRevision:
    draft = db.execute(
        select(WidgetConfigurationRevision)
        .where(
            WidgetConfigurationRevision.widget_id == widget.id,
            WidgetConfigurationRevision.organisation_id == widget.organisation_id,
            WidgetConfigurationRevision.workspace_id == widget.workspace_id,
            WidgetConfigurationRevision.status == "draft",
        )
        .order_by(WidgetConfigurationRevision.revision_number.desc())
    ).scalars().first()
    if draft is None:
        raise WidgetAdminNotFound("Draft configuration not found.")
    return draft


def update_draft(
    db: Session,
    *,
    widget: Widget,
    actor_user_id: str | None,
    payload: dict[str, Any],
    expected_concurrency_version: int,
) -> WidgetConfigurationRevision:
    draft = get_current_draft(db, widget=widget)
    if draft.concurrency_version != expected_concurrency_version:
        raise WidgetAdminConflict("Draft has changed since it was loaded.")
    try:
        values = validate_configuration_payload(payload, partial=True, existing=draft)
    except WidgetValidationError as exc:
        raise WidgetAdminValidationError(str(exc), errors=[WidgetAdminFieldError("configuration", "invalid", str(exc))]) from exc
    for key, value in values.items():
        setattr(draft, key, value)
    draft.concurrency_version += 1
    draft.configuration_hash = _configuration_hash(_configuration_values(draft))
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_draft.updated",
        entity_type="widget_configuration_revision",
        entity_id=draft.id,
        new_status="draft",
        metadata_json={"widget_id": widget.id, "revision_number": draft.revision_number, "changed_fields": sorted(payload.keys())},
    )
    db.commit()
    db.refresh(draft)
    return draft


def publish_widget(
    db: Session,
    *,
    widget: Widget,
    actor_user_id: str | None,
    draft_revision_id: str,
    expected_concurrency_version: int,
) -> WidgetConfigurationRevision:
    draft = _get_revision(db, widget=widget, revision_id=draft_revision_id)
    if draft.status != "draft":
        raise WidgetAdminConflict("Only the current draft can be published.")
    current_draft = get_current_draft(db, widget=widget)
    if current_draft.id != draft.id:
        raise WidgetAdminConflict("Draft is no longer current.")
    if draft.concurrency_version != expected_concurrency_version:
        raise WidgetAdminConflict("Draft has changed since it was loaded.")
    _validate_publishability(db, widget=widget, draft=draft)

    published = _clone_revision(db, widget=widget, source=draft, status="published", actor_user_id=actor_user_id, published=True, source_revision_id=draft.id)
    previous_active = widget.active_published_revision_id
    widget.active_published_revision_id = published.id
    draft.status = "superseded"
    _clone_revision(db, widget=widget, source=published, status="draft", actor_user_id=actor_user_id, published=False, source_revision_id=published.id)
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget.published",
        entity_type="widget",
        entity_id=widget.id,
        previous_status=previous_active,
        new_status=published.id,
        metadata_json={"published_revision_id": published.id, "revision_number": published.revision_number},
    )
    db.commit()
    db.refresh(published)
    return published


def list_revisions(db: Session, *, widget: Widget) -> list[WidgetConfigurationRevision]:
    statement = (
        select(WidgetConfigurationRevision)
        .where(
            WidgetConfigurationRevision.widget_id == widget.id,
            WidgetConfigurationRevision.organisation_id == widget.organisation_id,
            WidgetConfigurationRevision.workspace_id == widget.workspace_id,
        )
        .order_by(WidgetConfigurationRevision.revision_number.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_revision(db: Session, *, widget: Widget, revision_id: str) -> WidgetConfigurationRevision:
    return _get_revision(db, widget=widget, revision_id=revision_id)


def rollback_widget(
    db: Session,
    *,
    widget: Widget,
    actor_user_id: str | None,
    target_revision_id: str,
    expected_active_revision_id: str,
) -> WidgetConfigurationRevision:
    if widget.active_published_revision_id != expected_active_revision_id:
        raise WidgetAdminConflict("Published configuration changed before rollback.")
    target = _get_revision(db, widget=widget, revision_id=target_revision_id)
    if target.status != "published":
        raise WidgetAdminValidationError("Rollback target is not a published revision.", errors=[WidgetAdminFieldError("target_revision_id", "invalid", "Target revision is not published.")])
    _validate_publishability(db, widget=widget, draft=target)
    current_draft = db.execute(
        select(WidgetConfigurationRevision)
        .where(WidgetConfigurationRevision.widget_id == widget.id, WidgetConfigurationRevision.status == "draft")
        .order_by(WidgetConfigurationRevision.revision_number.desc())
    ).scalars().first()
    if current_draft is not None:
        current_draft.status = "superseded"
    published = _clone_revision(db, widget=widget, source=target, status="published", actor_user_id=actor_user_id, published=True, source_revision_id=target.id)
    previous_active = widget.active_published_revision_id
    widget.active_published_revision_id = published.id
    _clone_revision(db, widget=widget, source=published, status="draft", actor_user_id=actor_user_id, published=False, source_revision_id=published.id)
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_configuration.rolled_back",
        entity_type="widget",
        entity_id=widget.id,
        previous_status=previous_active,
        new_status=published.id,
        metadata_json={"target_revision_id": target.id, "published_revision_id": published.id, "revision_number": published.revision_number},
    )
    db.commit()
    db.refresh(published)
    return published


def active_published_revision(db: Session, *, widget: Widget) -> WidgetConfigurationRevision | None:
    if not widget.active_published_revision_id:
        return None
    return db.execute(
        select(WidgetConfigurationRevision).where(
            WidgetConfigurationRevision.id == widget.active_published_revision_id,
            WidgetConfigurationRevision.widget_id == widget.id,
            WidgetConfigurationRevision.status == "published",
        )
    ).scalar_one_or_none()


def diff_draft_to_published(db: Session, *, widget: Widget) -> dict[str, Any]:
    draft = get_current_draft(db, widget=widget)
    published = active_published_revision(db, widget=widget)
    if published is None:
        return {"changed_fields": list(CONFIG_FIELDS), "has_published_revision": False}
    changed = [field for field in CONFIG_FIELDS if getattr(draft, field) != getattr(published, field)]
    return {"changed_fields": changed, "has_published_revision": True}


def _get_revision(db: Session, *, widget: Widget, revision_id: str) -> WidgetConfigurationRevision:
    revision = db.execute(
        select(WidgetConfigurationRevision).where(
            WidgetConfigurationRevision.id == revision_id,
            WidgetConfigurationRevision.widget_id == widget.id,
            WidgetConfigurationRevision.organisation_id == widget.organisation_id,
            WidgetConfigurationRevision.workspace_id == widget.workspace_id,
        )
    ).scalar_one_or_none()
    if revision is None:
        raise WidgetAdminNotFound("Revision not found.")
    return revision


def _next_revision_number(db: Session, widget_id: str) -> int:
    current = db.execute(select(func.max(WidgetConfigurationRevision.revision_number)).where(WidgetConfigurationRevision.widget_id == widget_id)).scalar_one()
    return int(current or 0) + 1


def _clone_revision(
    db: Session,
    *,
    widget: Widget,
    source: WidgetConfigurationRevision,
    status: str,
    actor_user_id: str | None,
    published: bool,
    source_revision_id: str | None,
) -> WidgetConfigurationRevision:
    values = _configuration_values(source)
    revision = WidgetConfigurationRevision(
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        widget_id=widget.id,
        public_credential_id=widget.public_credential_id,
        revision_number=_next_revision_number(db, widget.id),
        status=status,
        concurrency_version=1,
        configuration_hash=_configuration_hash(values),
        source_revision_id=source_revision_id,
        created_by_user_id=actor_user_id,
        published_by_user_id=actor_user_id if published else None,
        published_at=utc_now() if published else None,
        **values,
    )
    db.add(revision)
    db.flush()
    return revision


def _validate_publishability(db: Session, *, widget: Widget, draft: WidgetConfigurationRevision) -> None:
    errors: list[WidgetAdminFieldError] = []
    try:
        validate_configuration_payload(_configuration_values(draft))
    except WidgetValidationError as exc:
        errors.append(WidgetAdminFieldError("configuration", "invalid", str(exc)))
    credential = get_credential(db, organisation_id=widget.organisation_id, workspace_id=widget.workspace_id, credential_id=widget.public_credential_id)
    if credential.status != "active":
        errors.append(WidgetAdminFieldError("public_key", "inactive", "Public widget key must be active before publishing."))
    if widget.operational_status != "enabled":
        errors.append(WidgetAdminFieldError("operational_status", "disabled", "Widget must be enabled before publishing."))
    origins = list_active_origins_for_credential(db, credential_id=widget.public_credential_id, environment=credential.environment)
    if not origins:
        errors.append(WidgetAdminFieldError("allowed_origins", "required", "At least one allowed origin is required before publishing."))
    if errors:
        raise WidgetAdminValidationError("Widget is not publishable.", errors=errors)


def _configuration_values(revision: WidgetConfigurationRevision) -> dict[str, Any]:
    return {field: getattr(revision, field) for field in CONFIG_FIELDS}


def _configuration_hash(values: dict[str, Any]) -> str:
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _contains_html(value: str) -> bool:
    return "<" in value or ">" in value or "javascript:" in value.lower()
from __future__ import annotations

import html
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access.credentials.service import CredentialValidationError, OriginNotFound, OriginValidationError, add_origin, create_credential, deactivate_origin, generate_unique_public_identifier, get_credential, list_origins
from app.access.origin_validation.repository import list_active_origins_for_credential
from app.access.widget_config.service import default_widget_payload, validate_configuration_payload
from app.access.widget_config.validation import WidgetValidationError
from app.db.models import CredentialAllowedOrigin, PublicCredential, Widget, WidgetConfigurationRevision
from app.repositories.audit_repository import add_audit_event

MAX_WIDGET_ORIGINS = 20
VALID_EMBED_VERSION_MODES = {"managed_major", "pinned"}
REPO_ROOT = Path(__file__).resolve().parents[5]

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

def list_widget_origins(db: Session, *, widget: Widget, active_only: bool = False) -> list[CredentialAllowedOrigin]:
    return list_origins(db, organisation_id=widget.organisation_id, workspace_id=widget.workspace_id, credential_id=widget.public_credential_id, active_only=active_only)


def add_widget_origin(db: Session, *, widget: Widget, origin: str, actor_user_id: str | None) -> CredentialAllowedOrigin:
    if "*" in origin:
        raise WidgetAdminValidationError("Wildcard origins are not supported for widget administration.", errors=[WidgetAdminFieldError("origin", "wildcard_not_supported", "Use exact origins only.")])
    active = list_widget_origins(db, widget=widget, active_only=True)
    if len(active) >= MAX_WIDGET_ORIGINS:
        raise WidgetAdminValidationError("Widget origin limit reached.", errors=[WidgetAdminFieldError("origin", "limit_reached", f"A widget may have at most {MAX_WIDGET_ORIGINS} active origins.")])
    try:
        row = add_origin(
            db,
            organisation_id=widget.organisation_id,
            workspace_id=widget.workspace_id,
            credential_id=widget.public_credential_id,
            origin=origin,
            wildcard_subdomains=False,
            actor_user_id=actor_user_id,
        )
    except OriginValidationError as exc:
        raise WidgetAdminValidationError(str(exc), errors=[WidgetAdminFieldError("origin", "invalid", str(exc))]) from exc
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_origin_added",
        entity_type="widget",
        entity_id=widget.id,
        metadata_json={"origin_id": row.id, "canonical_origin": origin_to_string(row)},
    )
    db.commit()
    return row


def remove_widget_origin(db: Session, *, widget: Widget, origin_id: str, actor_user_id: str | None) -> CredentialAllowedOrigin:
    active = list_widget_origins(db, widget=widget, active_only=True)
    if widget.active_published_revision_id and widget.operational_status == "enabled" and len(active) <= 1 and any(origin.id == origin_id for origin in active):
        raise WidgetAdminValidationError("Cannot remove the final active origin from a published enabled widget.", errors=[WidgetAdminFieldError("origin_id", "final_origin", "Disable the widget or add another origin before removing this one.")])
    try:
        row = deactivate_origin(
            db,
            organisation_id=widget.organisation_id,
            workspace_id=widget.workspace_id,
            credential_id=widget.public_credential_id,
            origin_id=origin_id,
            actor_user_id=actor_user_id,
        )
    except OriginNotFound as exc:
        raise WidgetAdminNotFound("Origin not found.") from exc
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_origin_removed",
        entity_type="widget",
        entity_id=widget.id,
        metadata_json={"origin_id": row.id, "canonical_origin": origin_to_string(row)},
    )
    db.commit()
    return row


def rotate_widget_public_key(db: Session, *, widget: Widget, actor_user_id: str | None, expected_public_credential_id: str) -> dict[str, Any]:
    old = get_credential(db, organisation_id=widget.organisation_id, workspace_id=widget.workspace_id, credential_id=widget.public_credential_id)
    if old.id != expected_public_credential_id:
        raise WidgetAdminConflict("Public key changed before rotation.")
    if old.status not in {"active", "disabled", "draft"}:
        raise WidgetAdminValidationError("Public key cannot be rotated from its current state.", errors=[WidgetAdminFieldError("public_credential_id", "terminal", "Terminal public keys cannot be rotated.")])
    now = utc_now()
    group_id = old.rotation_group_id or _stable_group_id()
    old.rotation_group_id = group_id
    old.rotated_at = now
    old.revoked_at = now
    old.status = "revoked"
    replacement = PublicCredential(
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        credential_type=old.credential_type,
        public_identifier=generate_unique_public_identifier(db, credential_type=old.credential_type, environment=old.environment),
        secret_hash=None,
        display_name=f"{old.display_name} replacement",
        status="active" if old.activated_at is not None else "draft",
        environment=old.environment,
        policy_profile=old.policy_profile,
        capabilities_json=list(old.capabilities_json or []),
        created_by_user_id=actor_user_id,
        rotation_group_id=group_id,
        parent_credential_id=old.id,
        activated_at=now if old.activated_at is not None else None,
        expires_at=old.expires_at,
        metadata_json={"rotation": "widget_immediate_cutover"},
    )
    db.add(replacement)
    db.flush()
    for origin in list_origins(db, organisation_id=widget.organisation_id, workspace_id=widget.workspace_id, credential_id=old.id, active_only=True):
        db.add(
            CredentialAllowedOrigin(
                organisation_id=widget.organisation_id,
                workspace_id=widget.workspace_id,
                credential_id=replacement.id,
                scheme=origin.scheme,
                hostname=origin.hostname,
                port=origin.port,
                wildcard_subdomains=origin.wildcard_subdomains,
                environment=origin.environment,
                active=True,
            )
        )
    widget.public_credential_id = replacement.id
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_public_key_rotated",
        entity_type="widget",
        entity_id=widget.id,
        previous_status=old.id,
        new_status=replacement.id,
        metadata_json={"old_key_fingerprint": _fingerprint(old.public_identifier), "new_key_fingerprint": _fingerprint(replacement.public_identifier), "embed_update_required": True},
    )
    db.commit()
    db.refresh(widget)
    db.refresh(replacement)
    return {"old_credential": old, "new_credential": replacement, "embed_update_required": True, "old_key_revoked": True}


def get_embed_metadata(db: Session, *, widget: Widget) -> dict[str, Any]:
    manifest = load_release_metadata()
    selected = resolve_widget_sdk_selection(widget, manifest=manifest)
    active = active_published_revision(db, widget=widget)
    origins = list_widget_origins(db, widget=widget, active_only=True)
    readiness = embed_readiness_codes(widget=widget, active_revision=active, active_origins=origins, selected=selected)
    snippet = generate_embed_snippet(public_key=widget.public_credential.public_identifier, loader_url=selected["loader_url"], integrity=selected.get("integrity"))
    return {
        "public_key": widget.public_credential.public_identifier,
        "public_key_status": widget.public_credential.status,
        "public_key_created_at": widget.public_credential.created_at,
        "public_key_rotated_at": widget.public_credential.rotated_at,
        "publication_status": "published" if active else "draft",
        "published": active is not None,
        "operational_status": widget.operational_status,
        "pilot_status": widget.pilot_status,
        "release_channel": widget.release_channel,
        "version_mode": widget.embed_version_mode,
        "pinned_sdk_version": widget.pinned_sdk_version,
        "selected_sdk_version": selected["sdk_version"],
        "selected_loader_path": selected["loader_path"],
        "protocol_major": selected["protocol_major"],
        "api_version": selected["api_version"],
        "sri": selected.get("integrity"),
        "snippet": snippet,
        "allowed_origins": [origin_to_dict(origin) for origin in origins],
        "active_published_revision_id": widget.active_published_revision_id,
        "active_revision_number": active.revision_number if active else None,
        "readiness": readiness,
        "active": readiness == ["ready"],
        "embed_update_required": bool(widget.public_credential.parent_credential_id),
    }


def update_embed_preference(db: Session, *, widget: Widget, version_mode: str, pinned_sdk_version: str | None, actor_user_id: str | None) -> dict[str, Any]:
    manifest = load_release_metadata()
    if version_mode not in VALID_EMBED_VERSION_MODES:
        raise WidgetAdminValidationError("Embed version mode is not supported.", errors=[WidgetAdminFieldError("version_mode", "unsupported", "Use managed_major or pinned.")])
    if version_mode == "managed_major":
        pinned_sdk_version = None
    if version_mode == "pinned" and not pinned_sdk_version:
        raise WidgetAdminValidationError("Pinned SDK version is required.", errors=[WidgetAdminFieldError("pinned_sdk_version", "required", "Select a supported SDK version.")])
    resolve_sdk_version(version_mode=version_mode, pinned_sdk_version=pinned_sdk_version, manifest=manifest)
    previous = {"version_mode": widget.embed_version_mode, "pinned_sdk_version": widget.pinned_sdk_version}
    widget.embed_version_mode = version_mode
    widget.pinned_sdk_version = pinned_sdk_version
    add_audit_event(
        db,
        organisation_id=widget.organisation_id,
        workspace_id=widget.workspace_id,
        actor_user_id=actor_user_id,
        action="widget_embed_version_changed",
        entity_type="widget",
        entity_id=widget.id,
        metadata_json={"before": previous, "after": {"version_mode": version_mode, "pinned_sdk_version": pinned_sdk_version}},
    )
    db.commit()
    db.refresh(widget)
    return get_embed_metadata(db, widget=widget)


def list_supported_sdk_versions() -> dict[str, Any]:
    manifest = load_release_metadata()
    versions = manifest["versions"]
    return {"recommended": manifest["recommended"], "versions": versions}


def load_release_metadata() -> dict[str, Any]:
    registry_path = REPO_ROOT / "deployment" / "widget" / "sdk-versions.json"
    if not registry_path.is_file():
        raise WidgetAdminValidationError("Supported SDK metadata is unavailable.", errors=[WidgetAdminFieldError("sdk_versions", "unavailable", "Supported SDK metadata is unavailable.")])
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    artifact_path = REPO_ROOT / "artifacts" / "widget-release" / "manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8")) if artifact_path.is_file() else None
    versions = []
    for item in registry.get("versions", []):
        enriched = dict(item)
        if artifact and artifact.get("sdk_version") == item.get("version"):
            enriched["immutable_loader_path"] = artifact.get("immutable_loader_path", enriched.get("immutable_loader_path"))
            enriched["major_alias_path"] = artifact.get("major_alias_path", enriched.get("major_alias_path"))
            enriched["integrity"] = (artifact.get("sri") or {}).get("immutable_loader")
        versions.append(enriched)
    if not versions:
        raise WidgetAdminValidationError("No supported SDK versions are configured.", errors=[WidgetAdminFieldError("sdk_versions", "unavailable", "No supported SDK versions are configured.")])
    return {"recommended": registry.get("recommended") or versions[0]["version"], "versions": versions}


def resolve_widget_sdk_selection(widget: Widget, *, manifest: dict[str, Any]) -> dict[str, Any]:
    return resolve_sdk_version(version_mode=widget.embed_version_mode, pinned_sdk_version=widget.pinned_sdk_version, manifest=manifest)


def resolve_sdk_version(*, version_mode: str, pinned_sdk_version: str | None, manifest: dict[str, Any]) -> dict[str, Any]:
    versions = manifest["versions"]
    if version_mode == "managed_major":
        target = next((item for item in versions if item["version"] == manifest["recommended"]), versions[0])
        if target.get("support_status") == "revoked":
            raise WidgetAdminValidationError("Recommended SDK version is revoked.", errors=[WidgetAdminFieldError("sdk_version", "revoked", "Recommended SDK version is not selectable.")])
        return _selection(target, mode="managed_major")
    if version_mode == "pinned":
        target = next((item for item in versions if item["version"] == pinned_sdk_version), None)
        if target is None:
            raise WidgetAdminValidationError("Pinned SDK version is not supported.", errors=[WidgetAdminFieldError("pinned_sdk_version", "unsupported", "Select a supported SDK version.")])
        if target.get("support_status") == "revoked":
            raise WidgetAdminValidationError("Pinned SDK version is revoked.", errors=[WidgetAdminFieldError("pinned_sdk_version", "revoked", "Select a supported SDK version.")])
        return _selection(target, mode="pinned")
    raise WidgetAdminValidationError("Embed version mode is not supported.", errors=[WidgetAdminFieldError("version_mode", "unsupported", "Use managed_major or pinned.")])


def _selection(version: dict[str, Any], *, mode: str) -> dict[str, Any]:
    loader_path = version["major_alias_path"] if mode == "managed_major" else version["immutable_loader_path"]
    cdn_origin = "https://cdn.example.com"
    return {
        "sdk_version": version["version"],
        "loader_path": loader_path,
        "loader_url": f"{cdn_origin}{loader_path}",
        "protocol_major": int(version["protocol_major"]),
        "api_version": version["api_version"],
        "integrity": version.get("integrity") if mode == "pinned" else None,
        "support_status": version.get("support_status", "supported"),
    }


def generate_embed_snippet(*, public_key: str, loader_url: str, integrity: str | None = None) -> str:
    attrs = [
        ("async", None),
        ("src", loader_url),
        ("data-widget-key", public_key),
    ]
    if integrity:
        attrs.append(("integrity", integrity))
        attrs.append(("crossorigin", "anonymous"))
    rendered = []
    for name, value in attrs:
        rendered.append(name if value is None else f'{name}="{html.escape(str(value), quote=True)}"')
    return f"<script {' '.join(rendered)}></script>"


def embed_readiness_codes(*, widget: Widget, active_revision: WidgetConfigurationRevision | None, active_origins: list[CredentialAllowedOrigin], selected: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    if active_revision is None:
        codes.append("unpublished")
    if not active_origins:
        codes.append("no_allowed_origins")
    if widget.operational_status != "enabled":
        codes.append("operationally_disabled")
    if widget.pilot_status != "approved":
        codes.append("pilot_not_enabled")
    if selected.get("support_status") != "supported":
        codes.append("unsupported_sdk_version")
    return codes or ["ready"]


def origin_to_dict(origin: CredentialAllowedOrigin) -> dict[str, Any]:
    return {
        "id": origin.id,
        "origin": origin_to_string(origin),
        "scheme": origin.scheme,
        "hostname": origin.hostname,
        "port": origin.port,
        "wildcard_subdomains": origin.wildcard_subdomains,
        "environment": origin.environment,
        "active": origin.active,
        "created_at": origin.created_at,
        "updated_at": origin.updated_at,
    }


def origin_to_string(origin: CredentialAllowedOrigin) -> str:
    host = f"*.{origin.hostname}" if origin.wildcard_subdomains else origin.hostname
    port = f":{origin.port}" if origin.port is not None else ""
    return f"{origin.scheme}://{host}{port}"


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _stable_group_id() -> str:
    from uuid import uuid4

    return str(uuid4())

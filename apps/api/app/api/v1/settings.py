from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.core.config import settings
from app.repositories.audit_repository import add_audit_event
from app.repositories.membership_repository import list_memberships_for_organisation
from app.repositories.organisation_repository import get_active_organisation
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.settings import (
    SettingsCapabilities,
    SettingsMembershipSummary,
    SettingsOperationalRead,
    SettingsOrganisationRead,
    SettingsWorkspaceRead,
    WorkspaceSettingsRead,
    WorkspaceSettingsUpdate,
)

router = APIRouter()

WorkspaceSettingsReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "contributor", "viewer"})),
]

WorkspaceSettingsManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]

EDITABLE_FIELDS = ["workspace.name", "workspace.default_language"]
READ_ONLY_FIELDS = [
    "workspace.id",
    "workspace.slug",
    "workspace.status",
    "organisation.id",
    "organisation.name",
    "organisation.slug",
    "organisation.status",
    "organisation.plan_key",
    "membership_summary",
]
ENVIRONMENT_CONTROLLED_FIELDS = [
    "environment",
    "service_name",
    "version",
    "phase",
    "public_widgets_enabled",
    "public_widget_messages_enabled",
    "public_widget_pilot_enforcement_enabled",
    "retrieval_max_context_chunks",
    "retrieval_max_context_chars",
    "chunk_size_words",
    "chunk_overlap_words",
    "embedding_provider",
    "embedding_model",
    "embedding_dimension",
    "default_ai_provider_key",
    "default_ai_model_key",
    "ai_request_timeout_seconds",
]
SECRET_MANAGED_FIELDS = [
    "database_url",
    "redis_url",
    "application_insights_connection_string",
    "rate_limit_identity_secret",
    "public_session_token_secret",
    "provider_api_keys",
]
UNSUPPORTED_FIELDS = [
    "organisation_update",
    "workspace_slug_update",
    "provider_secret_editing",
    "global_kill_switch_controls",
    "notification_preferences",
    "audit_retention_policy",
]


@router.get("/{workspace_id}/settings")
def get_workspace_settings(
    workspace_id: str,
    db: DbSession,
    _current_user: WorkspaceSettingsReaderDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    workspace = _load_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")

    response = WorkspaceSettingsRead(
        workspace=SettingsWorkspaceRead.model_validate(workspace),
        organisation=SettingsOrganisationRead.model_validate(organisation),
        membership_summary=_membership_summary(db, organisation_id=organisation_id),
        operational=_safe_operational_settings(),
        capabilities=_capabilities(),
    )
    return success_response(response.model_dump(mode="json"))


@router.patch("/{workspace_id}/settings")
def update_workspace_settings(
    workspace_id: str,
    payload: WorkspaceSettingsUpdate,
    db: DbSession,
    current_user: WorkspaceSettingsManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    workspace = _load_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found.")

    if payload.expected_updated_at and not _timestamp_matches(workspace.updated_at, payload.expected_updated_at):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace settings were updated by another request.")

    changed_fields: list[str] = []
    previous = {"name": workspace.name, "default_language": workspace.default_language}
    if workspace.name != payload.name:
        workspace.name = payload.name
        changed_fields.append("name")
    if workspace.default_language != payload.default_language:
        workspace.default_language = payload.default_language
        changed_fields.append("default_language")

    if changed_fields:
        add_audit_event(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            actor_user_id=current_user.user_id,
            action="workspace.settings.updated",
            entity_type="workspace",
            entity_id=workspace_id,
            previous_status=workspace.status,
            new_status=workspace.status,
            metadata_json={
                "changed_fields": changed_fields,
                "previous": {field: previous[field] for field in changed_fields},
                "updated": {"name": workspace.name, "default_language": workspace.default_language},
            },
        )

    db.commit()
    db.refresh(workspace)

    response = WorkspaceSettingsRead(
        workspace=SettingsWorkspaceRead.model_validate(workspace),
        organisation=SettingsOrganisationRead.model_validate(organisation),
        membership_summary=_membership_summary(db, organisation_id=organisation_id),
        operational=_safe_operational_settings(),
        capabilities=_capabilities(),
    )
    return success_response(response.model_dump(mode="json"))


def _load_workspace(db: DbSession, *, organisation_id: str, workspace_id: str):
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")
    return workspace


def _membership_summary(db: DbSession, *, organisation_id: str) -> SettingsMembershipSummary:
    memberships = list_memberships_for_organisation(db, organisation_id=organisation_id)
    active = sum(1 for membership in memberships if membership.status == "active")
    administrators = sum(1 for membership in memberships if membership.role in {"org_owner", "client_admin"})
    return SettingsMembershipSummary(
        total=len(memberships),
        active=active,
        inactive=len(memberships) - active,
        administrators=administrators,
    )


def _safe_operational_settings() -> SettingsOperationalRead:
    return SettingsOperationalRead(
        environment=settings.APP_ENV,
        service_name=settings.SERVICE_NAME,
        version=settings.VERSION,
        phase=settings.PHASE,
        public_widgets_enabled=_truthy(settings.PUBLIC_WIDGETS_ENABLED),
        public_widget_messages_enabled=_truthy(settings.PUBLIC_WIDGET_MESSAGES_ENABLED),
        public_widget_pilot_enforcement_enabled=_truthy(settings.PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED),
        retrieval_max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
        retrieval_max_context_chars=settings.RETRIEVAL_MAX_CONTEXT_CHARS,
        chunk_size_words=settings.CHUNK_SIZE_WORDS,
        chunk_overlap_words=settings.CHUNK_OVERLAP_WORDS,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_dimension=settings.EMBEDDING_DIMENSION,
        default_ai_provider_key=settings.DEFAULT_AI_PROVIDER_KEY,
        default_ai_model_key=settings.DEFAULT_AI_MODEL_KEY,
        ai_request_timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
    )


def _capabilities() -> SettingsCapabilities:
    return SettingsCapabilities(
        editable_fields=EDITABLE_FIELDS,
        read_only_fields=READ_ONLY_FIELDS,
        environment_controlled_fields=ENVIRONMENT_CONTROLLED_FIELDS,
        secret_managed_fields=SECRET_MANAGED_FIELDS,
        unsupported_fields=UNSUPPORTED_FIELDS,
    )


def _truthy(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _timestamp_matches(actual, expected: str) -> bool:
    variants = {actual.isoformat()}
    if actual.tzinfo is None:
        variants.add(actual.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"))
    else:
        variants.add(actual.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
    return expected in variants

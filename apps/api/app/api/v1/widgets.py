from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.access.widget_admin.service import (
    CONFIG_FIELDS,
    WidgetAdminConflict,
    WidgetAdminNotFound,
    WidgetAdminValidationError,
    active_published_revision,
    add_widget_origin,
    create_widget,
    create_preview_grant,
    diff_draft_to_published,
    get_current_draft,
    get_embed_metadata,
    list_installation_status,
    list_knowledge_options,
    get_revision,
    get_widget,
    list_revisions,
    list_supported_sdk_versions,
    list_widget_origins,
    list_widgets,
    publish_widget,
    remove_widget_origin,
    rollback_widget,
    rotate_widget_public_key,
    update_draft,
    update_draft_knowledge_scope,
    validate_publishability,
    update_embed_preference,
)
from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.db.models import CredentialAllowedOrigin, Widget, WidgetConfigurationRevision
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.widget_admin import (
    WidgetConfigurationPayload,
    WidgetCreateRequest,
    WidgetDetail,
    WidgetEmbedMetadata,
    WidgetInstallationStatus,
    WidgetKnowledgeOption,
    WidgetKnowledgeScopeUpdateRequest,
    WidgetEmbedPreferenceUpdateRequest,
    WidgetDraftUpdateRequest,
    WidgetOriginCreateRequest,
    WidgetOriginRead,
    WidgetPreviewGrantRequest,
    WidgetPreviewGrantResult,
    WidgetPublicationResult,
    WidgetPublicKeyRotateRequest,
    WidgetPublicKeyRotationResult,
    WidgetPublishRequest,
    WidgetPublishValidationResult,
    WidgetRevisionDetail,
    WidgetRevisionSummary,
    WidgetRollbackRequest,
    WidgetRollbackResult,
    WidgetSummary,
    WidgetSupportedSdkVersionsResponse,
    WidgetValidationErrorItem,
)
router = APIRouter()

WidgetAdminDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


def ensure_workspace_in_organisation(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


@router.get("/{workspace_id}/widgets")
def list_admin_widgets(
    workspace_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    return success_response([_widget_summary(db, widget).model_dump(mode="json") for widget in list_widgets(db, organisation_id=organisation_id, workspace_id=workspace_id)])


@router.post("/{workspace_id}/widgets", status_code=status.HTTP_201_CREATED)
def create_admin_widget(
    workspace_id: str,
    payload: WidgetCreateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        initial = payload.initial_configuration.model_dump(exclude_none=True) if payload.initial_configuration else None
        widget = create_widget(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            display_name=payload.display_name,
            environment=payload.environment,
            actor_user_id=current_user.user_id,
            initial_configuration=initial,
        )
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Widget identity already exists.") from exc
    return success_response(_widget_detail(db, widget).model_dump(mode="json"))


@router.get("/{workspace_id}/widgets/{widget_id}")
def get_admin_widget(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response(_widget_detail(db, widget).model_dump(mode="json"))


@router.get("/{workspace_id}/widgets/{widget_id}/draft")
def get_admin_widget_draft(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        draft = get_current_draft(db, widget=widget)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_response(_revision_detail(draft, widget).model_dump(mode="json"))


@router.patch("/{workspace_id}/widgets/{widget_id}/draft")
def update_admin_widget_draft(
    workspace_id: str,
    widget_id: str,
    payload: WidgetDraftUpdateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    update_payload = payload.model_dump(exclude_none=True)
    expected = int(update_payload.pop("expected_concurrency_version"))
    try:
        draft = update_draft(db, widget=widget, actor_user_id=current_user.user_id, payload=update_payload, expected_concurrency_version=expected)
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(_revision_detail(draft, widget).model_dump(mode="json"))



@router.get("/{workspace_id}/widgets/{widget_id}/knowledge-options")
def list_admin_widget_knowledge_options(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response([WidgetKnowledgeOption.model_validate(item).model_dump(mode="json") for item in list_knowledge_options(db, widget=widget)])


@router.patch("/{workspace_id}/widgets/{widget_id}/draft/knowledge")
def update_admin_widget_knowledge_scope(
    workspace_id: str,
    widget_id: str,
    payload: WidgetKnowledgeScopeUpdateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        draft = update_draft_knowledge_scope(db, widget=widget, actor_user_id=current_user.user_id, document_ids=payload.document_ids, expected_concurrency_version=payload.expected_concurrency_version)
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(_revision_detail(draft, widget).model_dump(mode="json"))


@router.post("/{workspace_id}/widgets/{widget_id}/validate-publish")
def validate_admin_widget_publish(
    workspace_id: str,
    widget_id: str,
    payload: WidgetPublishRequest,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        result = validate_publishability(db, widget=widget, draft_revision_id=payload.draft_revision_id, expected_concurrency_version=payload.expected_concurrency_version)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_response(_publish_validation_response(result).model_dump(mode="json"))


@router.post("/{workspace_id}/widgets/{widget_id}/preview-grant")
def create_admin_widget_preview_grant(
    workspace_id: str,
    widget_id: str,
    payload: WidgetPreviewGrantRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        result = create_preview_grant(db, widget=widget, actor_user_id=current_user.user_id, draft_revision_id=payload.draft_revision_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(WidgetPreviewGrantResult.model_validate(result).model_dump(mode="json"))
@router.post("/{workspace_id}/widgets/{widget_id}/publish")
def publish_admin_widget(
    workspace_id: str,
    widget_id: str,
    payload: WidgetPublishRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        published = publish_widget(db, widget=widget, actor_user_id=current_user.user_id, draft_revision_id=payload.draft_revision_id, expected_concurrency_version=payload.expected_concurrency_version)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    db.refresh(widget)
    result = WidgetPublicationResult(widget=_widget_summary(db, widget), published_revision=_revision_detail(published, widget))
    return success_response(result.model_dump(mode="json"))


@router.get("/{workspace_id}/widgets/{widget_id}/revisions")
def list_admin_widget_revisions(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response([_revision_summary(revision, widget).model_dump(mode="json") for revision in list_revisions(db, widget=widget)])


@router.get("/{workspace_id}/widgets/{widget_id}/revisions/{revision_id}")
def get_admin_widget_revision(
    workspace_id: str,
    widget_id: str,
    revision_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        revision = get_revision(db, widget=widget, revision_id=revision_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_response(_revision_detail(revision, widget).model_dump(mode="json"))


@router.post("/{workspace_id}/widgets/{widget_id}/rollback")
def rollback_admin_widget(
    workspace_id: str,
    widget_id: str,
    payload: WidgetRollbackRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        published = rollback_widget(db, widget=widget, actor_user_id=current_user.user_id, target_revision_id=payload.target_revision_id, expected_active_revision_id=payload.expected_active_revision_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    db.refresh(widget)
    result = WidgetRollbackResult(
        widget=_widget_summary(db, widget),
        published_revision=_revision_detail(published, widget),
        rolled_back_from_revision_id=payload.target_revision_id,
    )
    return success_response(result.model_dump(mode="json"))


@router.get("/{workspace_id}/widgets/{widget_id}/origins")
def list_admin_widget_origins(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response([_origin_response(origin).model_dump(mode="json") for origin in list_widget_origins(db, widget=widget, active_only=False)])


@router.post("/{workspace_id}/widgets/{widget_id}/origins", status_code=status.HTTP_201_CREATED)
def add_admin_widget_origin(
    workspace_id: str,
    widget_id: str,
    payload: WidgetOriginCreateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        origin = add_widget_origin(db, widget=widget, origin=payload.origin, actor_user_id=current_user.user_id)
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(_origin_response(origin).model_dump(mode="json"))


@router.delete("/{workspace_id}/widgets/{widget_id}/origins/{origin_id}")
def remove_admin_widget_origin(
    workspace_id: str,
    widget_id: str,
    origin_id: str,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        origin = remove_widget_origin(db, widget=widget, origin_id=origin_id, actor_user_id=current_user.user_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(_origin_response(origin).model_dump(mode="json"))


@router.post("/{workspace_id}/widgets/{widget_id}/rotate-key")
def rotate_admin_widget_public_key(
    workspace_id: str,
    widget_id: str,
    payload: WidgetPublicKeyRotateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        result = rotate_widget_public_key(db, widget=widget, actor_user_id=current_user.user_id, expected_public_credential_id=payload.expected_public_credential_id)
    except WidgetAdminConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    new_credential = result["new_credential"]
    response = WidgetPublicKeyRotationResult(
        widget_id=widget.id,
        public_credential_id=new_credential.id,
        public_key=new_credential.public_identifier,
        public_key_status=new_credential.status,
        old_key_revoked=bool(result["old_key_revoked"]),
        embed_update_required=bool(result["embed_update_required"]),
        rotated_at=new_credential.activated_at or new_credential.created_at,
    )
    return success_response(response.model_dump(mode="json"))


@router.get("/{workspace_id}/widgets/{widget_id}/embed")
def get_admin_widget_embed(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        metadata = get_embed_metadata(db, widget=widget)
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(WidgetEmbedMetadata.model_validate(metadata).model_dump(mode="json"))


@router.patch("/{workspace_id}/widgets/{widget_id}/embed")
def update_admin_widget_embed(
    workspace_id: str,
    widget_id: str,
    payload: WidgetEmbedPreferenceUpdateRequest,
    db: DbSession,
    current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    try:
        metadata = update_embed_preference(db, widget=widget, version_mode=payload.version_mode, pinned_sdk_version=payload.pinned_sdk_version, actor_user_id=current_user.user_id)
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(WidgetEmbedMetadata.model_validate(metadata).model_dump(mode="json"))



@router.get("/{workspace_id}/widgets/{widget_id}/installation-status")
def get_admin_widget_installation_status(
    workspace_id: str,
    widget_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    widget = _load_widget_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    return success_response([WidgetInstallationStatus.model_validate(item).model_dump(mode="json") for item in list_installation_status(db, widget=widget)])
@router.get("/{workspace_id}/widget-sdk-versions")
def list_admin_widget_sdk_versions(
    workspace_id: str,
    db: DbSession,
    _current_user: WidgetAdminDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        metadata = list_supported_sdk_versions()
    except WidgetAdminValidationError as exc:
        raise _validation_http_error(exc) from exc
    return success_response(WidgetSupportedSdkVersionsResponse.model_validate(metadata).model_dump(mode="json"))

def _load_widget_or_404(db: DbSession, *, organisation_id: str, workspace_id: str, widget_id: str) -> Widget:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        return get_widget(db, organisation_id=organisation_id, workspace_id=workspace_id, widget_id=widget_id)
    except WidgetAdminNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.") from exc


def _widget_summary(db: DbSession, widget: Widget) -> WidgetSummary:
    draft = None
    try:
        draft = get_current_draft(db, widget=widget)
    except WidgetAdminNotFound:
        draft = None
    active = active_published_revision(db, widget=widget)
    credential = widget.public_credential
    return WidgetSummary(
        id=widget.id,
        display_name=widget.display_name,
        public_identifier=credential.public_identifier,
        public_credential_id=widget.public_credential_id,
        publication_status="published" if active is not None else "draft",
        active_revision_number=active.revision_number if active else None,
        active_published_revision_id=widget.active_published_revision_id,
        draft_revision_id=draft.id if draft else None,
        draft_dirty=bool(active is None or (draft is not None and any(getattr(draft, field) != getattr(active, field) for field in CONFIG_FIELDS))),
        operational_status=widget.operational_status,
        pilot_status=widget.pilot_status,
        release_channel=widget.release_channel,
        created_at=widget.created_at,
        updated_at=widget.updated_at,
    )


def _widget_detail(db: DbSession, widget: Widget) -> WidgetDetail:
    summary = _widget_summary(db, widget)
    draft = None
    try:
        draft = _revision_detail(get_current_draft(db, widget=widget), widget)
    except WidgetAdminNotFound:
        draft = None
    active = active_published_revision(db, widget=widget)
    return WidgetDetail(**summary.model_dump(), draft=draft, active_published_revision=_revision_summary(active, widget) if active else None, diff=diff_draft_to_published(db, widget=widget) if draft else None)


def _revision_summary(revision: WidgetConfigurationRevision, widget: Widget) -> WidgetRevisionSummary:
    return WidgetRevisionSummary(
        id=revision.id,
        revision_number=revision.revision_number,
        status=revision.status,
        is_active_published=widget.active_published_revision_id == revision.id,
        concurrency_version=revision.concurrency_version,
        created_by_user_id=revision.created_by_user_id,
        created_at=revision.created_at,
        published_by_user_id=revision.published_by_user_id,
        published_at=revision.published_at,
        source_revision_id=revision.source_revision_id,
    )


def _revision_detail(revision: WidgetConfigurationRevision, widget: Widget) -> WidgetRevisionDetail:
    return WidgetRevisionDetail(**_revision_summary(revision, widget).model_dump(), configuration=_configuration_payload(revision))


def _configuration_payload(revision: WidgetConfigurationRevision) -> WidgetConfigurationPayload:
    values: dict[str, Any] = {field: getattr(revision, field) for field in CONFIG_FIELDS}
    values["suggested_questions_json"] = list(values["suggested_questions_json"] or [])
    return WidgetConfigurationPayload(**values)


def _origin_response(origin: CredentialAllowedOrigin) -> WidgetOriginRead:
    host = f"*.{origin.hostname}" if origin.wildcard_subdomains else origin.hostname
    port = f":{origin.port}" if origin.port is not None else ""
    return WidgetOriginRead(
        id=origin.id,
        origin=f"{origin.scheme}://{host}{port}",
        scheme=origin.scheme,
        hostname=origin.hostname,
        port=origin.port,
        wildcard_subdomains=origin.wildcard_subdomains,
        environment=origin.environment,
        active=origin.active,
        created_at=origin.created_at,
        updated_at=origin.updated_at,
    )


def _publish_validation_response(result: dict[str, Any]) -> WidgetPublishValidationResult:
    return WidgetPublishValidationResult(
        publishable=bool(result["publishable"]),
        errors=[WidgetValidationErrorItem(field=item.field, code=item.code, message=item.message) for item in result["errors"]],
        warnings=[WidgetValidationErrorItem(field=item.field, code=item.code, message=item.message) for item in result["warnings"]],
        diff=result["diff"],
        knowledge=[WidgetKnowledgeOption.model_validate(item) for item in result["knowledge"]],
    )
def _validation_http_error(exc: WidgetAdminValidationError) -> HTTPException:
    errors = [WidgetValidationErrorItem(field=item.field, code=item.code, message=item.message).model_dump(mode="json") for item in exc.errors]
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "widget_not_publishable", "message": str(exc), "errors": errors})
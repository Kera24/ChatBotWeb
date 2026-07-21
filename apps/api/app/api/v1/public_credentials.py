from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.access.credentials.repository import list_rotation_group
from app.access.credentials.service import (
    CredentialNotFound,
    CredentialValidationError,
    OriginNotFound,
    OriginValidationError,
    add_origin,
    create_credential,
    deactivate_origin,
    get_credential,
    list_credentials,
    list_origins,
    rotate_credential,
    transition_credential,
    update_credential,
)
from app.access.widget_config.service import (
    WidgetConfigurationNotFound,
    publish_configuration,
    safe_public_configuration,
    upsert_draft_configuration,
    get_configuration,
)
from app.access.widget_config.validation import WidgetValidationError
from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.public_access import (
    CredentialOriginCreate,
    CredentialOriginRead,
    PublicCredentialCreate,
    PublicCredentialRead,
    PublicCredentialUpdate,
    WidgetConfigurationRead,
    WidgetConfigurationUpsert,
)

router = APIRouter()

PublicCredentialManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


def ensure_workspace_in_organisation(db: DbSession, *, organisation_id: str, workspace_id: str) -> None:
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")


@router.get("/{workspace_id}/public-credentials")
def list_public_credentials(
    workspace_id: str,
    db: DbSession,
    _current_user: PublicCredentialManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    credentials = list_credentials(db, organisation_id=organisation_id, workspace_id=workspace_id)
    data = [_credential_response(db, credential).model_dump(mode="json") for credential in credentials]
    return success_response(data)


@router.post("/{workspace_id}/public-credentials", status_code=status.HTTP_201_CREATED)
def create_public_credential(
    workspace_id: str,
    payload: PublicCredentialCreate,
    db: DbSession,
    current_user: PublicCredentialManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        credential = create_credential(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_type=payload.credential_type,
            display_name=payload.display_name,
            environment=payload.environment,
            policy_profile=payload.policy_profile,
            capabilities=payload.capabilities,
            expires_at=payload.expires_at,
            metadata_json=payload.metadata_json,
            created_by_user_id=current_user.user_id,
        )
    except CredentialValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential public identifier already exists.") from exc
    return success_response(_credential_response(db, credential).model_dump(mode="json"))


@router.get("/{workspace_id}/public-credentials/{credential_id}")
def get_public_credential(
    workspace_id: str,
    credential_id: str,
    db: DbSession,
    _current_user: PublicCredentialManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    credential = _load_credential_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    return success_response(_credential_response(db, credential).model_dump(mode="json"))


@router.patch("/{workspace_id}/public-credentials/{credential_id}")
def patch_public_credential(
    workspace_id: str,
    credential_id: str,
    payload: PublicCredentialUpdate,
    db: DbSession,
    current_user: PublicCredentialManagerDependency,
    organisation_id: str = Query(...),
) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        credential = update_credential(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
            actor_user_id=current_user.user_id,
            display_name=payload.display_name,
            policy_profile=payload.policy_profile,
            capabilities=payload.capabilities,
            expires_at=payload.expires_at,
        )
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except CredentialValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(_credential_response(db, credential).model_dump(mode="json"))


@router.post("/{workspace_id}/public-credentials/{credential_id}/activate")
def activate_public_credential(workspace_id: str, credential_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    return _transition_response(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, current_user=current_user, target_status="active")


@router.post("/{workspace_id}/public-credentials/{credential_id}/disable")
def disable_public_credential(workspace_id: str, credential_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    return _transition_response(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, current_user=current_user, target_status="disabled")


@router.post("/{workspace_id}/public-credentials/{credential_id}/revoke")
def revoke_public_credential(workspace_id: str, credential_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    return _transition_response(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, current_user=current_user, target_status="revoked")


@router.post("/{workspace_id}/public-credentials/{credential_id}/rotate", status_code=status.HTTP_201_CREATED)
def rotate_public_credential(workspace_id: str, credential_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        replacement = rotate_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, actor_user_id=current_user.user_id)
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except CredentialValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(_credential_response(db, replacement).model_dump(mode="json"))


@router.get("/{workspace_id}/public-credentials/{credential_id}/origins")
def list_public_credential_origins(workspace_id: str, credential_id: str, db: DbSession, _current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    _load_credential_or_404(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    origins = list_origins(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    return success_response([CredentialOriginRead.model_validate(origin).model_dump(mode="json") for origin in origins])


@router.post("/{workspace_id}/public-credentials/{credential_id}/origins", status_code=status.HTTP_201_CREATED)
def add_public_credential_origin(workspace_id: str, credential_id: str, payload: CredentialOriginCreate, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        origin = add_origin(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, origin=payload.origin, wildcard_subdomains=payload.wildcard_subdomains, actor_user_id=current_user.user_id)
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except OriginValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(CredentialOriginRead.model_validate(origin).model_dump(mode="json"))


@router.delete("/{workspace_id}/public-credentials/{credential_id}/origins/{origin_id}")
def remove_public_credential_origin(workspace_id: str, credential_id: str, origin_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        origin = deactivate_origin(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, origin_id=origin_id, actor_user_id=current_user.user_id)
    except OriginNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Origin not found for credential.") from exc
    return success_response(CredentialOriginRead.model_validate(origin).model_dump(mode="json"))


@router.get("/{workspace_id}/public-credentials/{credential_id}/widget-config")
def get_widget_config(workspace_id: str, credential_id: str, db: DbSession, _current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        configuration = get_configuration(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except WidgetConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget configuration not found for credential.") from exc
    return success_response(_widget_configuration_response(configuration).model_dump(mode="json"))


@router.put("/{workspace_id}/public-credentials/{credential_id}/widget-config")
def put_widget_config(workspace_id: str, credential_id: str, payload: WidgetConfigurationUpsert, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        configuration = upsert_draft_configuration(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
            actor_user_id=current_user.user_id,
            payload=payload.model_dump(exclude_unset=True),
        )
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except WidgetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(_widget_configuration_response(configuration).model_dump(mode="json"))


@router.post("/{workspace_id}/public-credentials/{credential_id}/widget-config/publish")
def publish_widget_config(workspace_id: str, credential_id: str, db: DbSession, current_user: PublicCredentialManagerDependency, organisation_id: str = Query(...)) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        configuration = publish_configuration(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, actor_user_id=current_user.user_id)
    except (CredentialNotFound, WidgetConfigurationNotFound) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget configuration not found for credential.") from exc
    return success_response(_widget_configuration_response(configuration).model_dump(mode="json"))


def _transition_response(db: DbSession, *, organisation_id: str, workspace_id: str, credential_id: str, current_user: DevelopmentCurrentUser, target_status: str) -> dict[str, object]:
    ensure_workspace_in_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    try:
        credential = transition_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id, target_status=target_status, actor_user_id=current_user.user_id)
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc
    except CredentialValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return success_response(_credential_response(db, credential).model_dump(mode="json"))


def _load_credential_or_404(db: DbSession, *, organisation_id: str, workspace_id: str, credential_id: str):
    try:
        return get_credential(db, organisation_id=organisation_id, workspace_id=workspace_id, credential_id=credential_id)
    except CredentialNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found for workspace.") from exc


def _credential_response(db: DbSession, credential) -> PublicCredentialRead:
    origins = list_origins(db, organisation_id=credential.organisation_id, workspace_id=credential.workspace_id, credential_id=credential.id)
    try:
        configuration = get_configuration(db, organisation_id=credential.organisation_id, workspace_id=credential.workspace_id, credential_id=credential.id)
    except WidgetConfigurationNotFound:
        configuration = None
    return PublicCredentialRead(
        id=credential.id,
        public_identifier=credential.public_identifier,
        credential_type=credential.credential_type,
        display_name=credential.display_name,
        status=credential.status,
        environment=credential.environment,
        policy_profile=credential.policy_profile,
        capabilities=list(credential.capabilities_json or []),
        created_by_user_id=credential.created_by_user_id,
        rotation_group_id=credential.rotation_group_id,
        parent_credential_id=credential.parent_credential_id,
        created_at=credential.created_at,
        updated_at=credential.updated_at,
        activated_at=credential.activated_at,
        rotated_at=credential.rotated_at,
        revoked_at=credential.revoked_at,
        expires_at=credential.expires_at,
        last_used_at=credential.last_used_at,
        deleted_at=credential.deleted_at,
        origin_count=len(origins),
        widget_configuration_status=configuration.status if configuration else None,
        widget_configuration_version=configuration.configuration_version if configuration else None,
    )


def _widget_configuration_response(configuration) -> WidgetConfigurationRead:
    return WidgetConfigurationRead(
        id=configuration.id,
        credential_id=configuration.credential_id,
        status=configuration.status,
        bot_name=configuration.bot_name,
        welcome_message=configuration.welcome_message,
        launcher_label=configuration.launcher_label,
        primary_colour=configuration.primary_colour,
        secondary_colour=configuration.secondary_colour,
        logo_path=configuration.logo_path,
        avatar_path=configuration.avatar_path,
        position=configuration.position,
        theme_mode=configuration.theme_mode,
        suggested_questions_json=list(configuration.suggested_questions_json or []),
        fallback_contact_text=configuration.fallback_contact_text,
        privacy_notice_text=configuration.privacy_notice_text,
        privacy_notice_url=configuration.privacy_notice_url,
        terms_url=configuration.terms_url,
        language=configuration.language,
        show_citations=configuration.show_citations,
        allow_conversation_history=configuration.allow_conversation_history,
        max_initial_suggestions=configuration.max_initial_suggestions,
        configuration_version=configuration.configuration_version,
        published_at=configuration.published_at,
        created_at=configuration.created_at,
        updated_at=configuration.updated_at,
        safe_public_configuration=safe_public_configuration(configuration),
    )

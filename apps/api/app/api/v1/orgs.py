from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.audit_repository import list_audit_events_for_organisation
from app.repositories.organisation_repository import get_active_organisation
from app.repositories.workspace_repository import (
    create_workspace_for_organisation,
    list_workspaces_for_organisation,
)
from app.schemas.audit import AuditEventRead
from app.schemas.common import success_response
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead

router = APIRouter()

WorkspaceManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


@router.get("/{organisation_id}/workspaces")
def list_workspaces(
    organisation_id: str,
    db: DbSession,
    _current_user: WorkspaceManagerDependency,
) -> dict[str, object]:
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found.",
        )

    workspaces = list_workspaces_for_organisation(db, organisation_id=organisation_id)
    data = [
        WorkspaceRead.model_validate(workspace).model_dump(mode="json")
        for workspace in workspaces
    ]
    return success_response(data)


@router.post("/{organisation_id}/workspaces", status_code=status.HTTP_201_CREATED)
def create_workspace(
    organisation_id: str,
    payload: WorkspaceCreate,
    db: DbSession,
    _current_user: WorkspaceManagerDependency,
) -> dict[str, object]:
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found.",
        )

    try:
        workspace = create_workspace_for_organisation(
            db,
            organisation_id=organisation_id,
            name=payload.name,
            slug=payload.slug,
            default_language=payload.default_language,
        )
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace slug already exists for this organisation.",
        ) from exc

    data = WorkspaceRead.model_validate(workspace).model_dump(mode="json")
    return success_response(data)


@router.get("/{organisation_id}/audit-events")
def list_organisation_audit_events(
    organisation_id: str,
    db: DbSession,
    _current_user: WorkspaceManagerDependency,
    limit: int = 100,
) -> dict[str, object]:
    organisation = get_active_organisation(db, organisation_id=organisation_id)
    if organisation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation not found.",
        )

    bounded_limit = min(max(limit, 1), 500)
    events = list_audit_events_for_organisation(
        db,
        organisation_id=organisation_id,
        limit=bounded_limit,
    )
    data = [AuditEventRead.model_validate(event).model_dump(mode="json") for event in events]
    return success_response(data, meta={"limit": bounded_limit})

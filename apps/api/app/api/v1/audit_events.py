from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.audit_repository import list_audit_events_for_workspace
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.audit import AuditEventRead
from app.schemas.common import success_response

router = APIRouter()

AuditReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


@router.get("/{workspace_id}/audit-events")
def list_workspace_audit_events(
    workspace_id: str,
    db: DbSession,
    _current_user: AuditReaderDependency,
    organisation_id: str = Query(
        ...,
        description="Temporary tenant context required until production auth can infer organisation access safely.",
    ),
    limit: int = 100,
) -> dict[str, object]:
    workspace = get_workspace_for_organisation(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
    )
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for organisation.",
        )

    bounded_limit = min(max(limit, 1), 500)
    events = list_audit_events_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        limit=bounded_limit,
    )
    data = [AuditEventRead.model_validate(event).model_dump(mode="json") for event in events]
    return success_response(data, meta={"limit": bounded_limit})

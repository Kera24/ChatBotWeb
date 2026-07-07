from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.workspace import WorkspaceRead

router = APIRouter()

WorkspaceViewerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str,
    db: DbSession,
    _current_user: WorkspaceViewerDependency,
    organisation_id: str = Query(
        ...,
        description=(
            "Temporary tenant context required until production auth can infer "
            "organisation access safely."
        ),
    ),
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

    data = WorkspaceRead.model_validate(workspace).model_dump(mode="json")
    return success_response(data)

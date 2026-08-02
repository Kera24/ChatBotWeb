from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, DevelopmentCurrentUser, require_organisation_role
from app.repositories.audit_repository import add_audit_event
from app.repositories.membership_repository import (
    VALID_MEMBERSHIP_STATUSES,
    VALID_ORGANISATION_ROLES,
    get_membership_by_id,
    list_memberships_for_organisation,
)
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.schemas.common import success_response
from app.schemas.membership import MembershipRead, MembershipRoleUpdate, MembershipStatusUpdate, MembershipUserRead

router = APIRouter()

MembershipReaderDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin", "viewer"})),
]
MembershipManagerDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_organisation_role({"org_owner", "client_admin"})),
]


@router.get("/{workspace_id}/memberships")
def list_workspace_memberships(
    workspace_id: str,
    db: DbSession,
    _current_user: MembershipReaderDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    workspace = _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    memberships = list_memberships_for_organisation(db, organisation_id=organisation_id)
    data = [_membership_response(membership, workspace_id=workspace.id, workspace_name=workspace.name, workspace_slug=workspace.slug) for membership in memberships]
    return success_response(data, meta={"count": len(data), "roles": sorted(VALID_ORGANISATION_ROLES), "statuses": sorted(VALID_MEMBERSHIP_STATUSES)})


@router.patch("/{workspace_id}/memberships/{membership_id}/role")
def update_workspace_membership_role(
    workspace_id: str,
    membership_id: str,
    payload: MembershipRoleUpdate,
    db: DbSession,
    current_user: MembershipManagerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    workspace = _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if payload.role not in VALID_ORGANISATION_ROLES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported membership role.")
    membership = _load_membership(db, organisation_id=organisation_id, membership_id=membership_id)
    previous_role = membership.role
    if previous_role != payload.role:
        membership.role = payload.role
        add_audit_event(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace.id,
            actor_user_id=current_user.user_id,
            action="membership.role.updated",
            entity_type="membership",
            entity_id=membership.id,
            previous_status=previous_role,
            new_status=payload.role,
            metadata_json={"target_user_id": membership.user_id},
        )
        db.commit()
        db.refresh(membership)
    return success_response(_membership_response(membership, workspace_id=workspace.id, workspace_name=workspace.name, workspace_slug=workspace.slug))


@router.patch("/{workspace_id}/memberships/{membership_id}/status")
def update_workspace_membership_status(
    workspace_id: str,
    membership_id: str,
    payload: MembershipStatusUpdate,
    db: DbSession,
    current_user: MembershipManagerDependency,
    organisation_id: str = Query(..., description="Temporary tenant context required until production auth can infer organisation access safely."),
) -> dict[str, object]:
    workspace = _ensure_workspace(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if payload.status not in VALID_MEMBERSHIP_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported membership status.")
    membership = _load_membership(db, organisation_id=organisation_id, membership_id=membership_id)
    if current_user.user_id == membership.user_id and payload.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current user cannot deactivate their own membership.")
    previous_status = membership.status
    if previous_status != payload.status:
        membership.status = payload.status
        add_audit_event(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace.id,
            actor_user_id=current_user.user_id,
            action="membership.status.updated",
            entity_type="membership",
            entity_id=membership.id,
            previous_status=previous_status,
            new_status=payload.status,
            metadata_json={"target_user_id": membership.user_id, "role": membership.role},
        )
        db.commit()
        db.refresh(membership)
    return success_response(_membership_response(membership, workspace_id=workspace.id, workspace_name=workspace.name, workspace_slug=workspace.slug))


def _ensure_workspace(db: DbSession, *, organisation_id: str, workspace_id: str):
    workspace = get_workspace_for_organisation(db, organisation_id=organisation_id, workspace_id=workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found for organisation.")
    return workspace


def _load_membership(db: DbSession, *, organisation_id: str, membership_id: str):
    membership = get_membership_by_id(db, organisation_id=organisation_id, membership_id=membership_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found for organisation.")
    return membership


def _membership_response(membership, *, workspace_id: str, workspace_name: str, workspace_slug: str) -> dict[str, object]:
    return MembershipRead(
        id=membership.id,
        organisation_id=membership.organisation_id,
        organisation_name=membership.organisation.name,
        organisation_slug=membership.organisation.slug,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        workspace_slug=workspace_slug,
        user=MembershipUserRead.model_validate(membership.user),
        role=membership.role,
        status=membership.status,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
    ).model_dump(mode="json")

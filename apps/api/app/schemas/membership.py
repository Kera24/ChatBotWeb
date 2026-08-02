from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_ORGANISATION_ROLES = ("org_owner", "client_admin", "contributor", "viewer")
SUPPORTED_MEMBERSHIP_STATUSES = ("active", "inactive")


class MembershipUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class MembershipRead(BaseModel):
    id: str
    organisation_id: str
    organisation_name: str
    organisation_slug: str
    workspace_id: str
    workspace_name: str
    workspace_slug: str
    user: MembershipUserRead
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class MembershipRoleUpdate(BaseModel):
    role: str = Field(..., min_length=1, max_length=40)


class MembershipStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=40)

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    default_language: str = Field(default="en", min_length=2, max_length=16)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    name: str
    slug: str
    status: str
    default_language: str
    created_at: datetime
    updated_at: datetime

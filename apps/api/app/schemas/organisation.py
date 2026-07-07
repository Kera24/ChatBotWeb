from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganisationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganisationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    status: str
    plan_key: str
    created_at: datetime
    updated_at: datetime

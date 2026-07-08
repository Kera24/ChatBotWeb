from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    actor_user_id: str | None
    action: str
    entity_type: str
    entity_id: str
    document_id: str | None
    document_version_id: str | None
    previous_status: str | None
    new_status: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

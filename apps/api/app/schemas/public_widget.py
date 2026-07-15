from pydantic import BaseModel, ConfigDict, Field


class PublicWidgetSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: str | None = Field(default=None, max_length=120)
    metadata: dict[str, str | int | float | bool | None] | None = None
    requested_language: str | None = Field(default=None, max_length=16)


class PublicWidgetSessionCapabilities(BaseModel):
    can_send_messages: bool
    conversation_history_enabled: bool
    citations_enabled: bool


class PublicWidgetSessionCreateResponse(BaseModel):
    session_token: str
    expires_at: str
    absolute_expires_at: str
    inactivity_timeout_seconds: int
    max_messages: int
    remaining_messages: int
    configuration_version: int
    capabilities: PublicWidgetSessionCapabilities
    request_id: str


class PublicWidgetErrorResponse(BaseModel):
    error: dict[str, object]
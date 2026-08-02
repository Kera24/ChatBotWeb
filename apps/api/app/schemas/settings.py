from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettingsWorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    name: str
    slug: str
    status: str
    default_language: str
    created_at: datetime
    updated_at: datetime


class SettingsOrganisationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    status: str
    plan_key: str
    created_at: datetime
    updated_at: datetime


class SettingsMembershipSummary(BaseModel):
    total: int
    active: int
    inactive: int
    administrators: int


class SettingsOperationalRead(BaseModel):
    environment: str
    service_name: str
    version: str
    phase: str
    public_widgets_enabled: bool
    public_widget_messages_enabled: bool
    public_widget_pilot_enforcement_enabled: bool
    retrieval_max_context_chunks: int
    retrieval_max_context_chars: int
    chunk_size_words: int
    chunk_overlap_words: int
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    default_ai_provider_key: str
    default_ai_model_key: str
    ai_request_timeout_seconds: float


class SettingsCapabilities(BaseModel):
    editable_fields: list[str]
    read_only_fields: list[str]
    environment_controlled_fields: list[str]
    secret_managed_fields: list[str]
    unsupported_fields: list[str]


class WorkspaceSettingsRead(BaseModel):
    workspace: SettingsWorkspaceRead
    organisation: SettingsOrganisationRead
    membership_summary: SettingsMembershipSummary
    operational: SettingsOperationalRead
    capabilities: SettingsCapabilities


class WorkspaceSettingsUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_language: str = Field(..., min_length=2, max_length=16)
    expected_updated_at: str | None = Field(default=None, max_length=80)

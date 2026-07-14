from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PublicCredentialCreate(BaseModel):
    credential_type: str = Field(default="widget_public_key", max_length=60)
    display_name: str = Field(min_length=1, max_length=160)
    environment: str = Field(default="development", max_length=40)
    policy_profile: str = Field(default="widget", max_length=80)
    capabilities: list[str] | None = None
    expires_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class PublicCredentialUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    policy_profile: str | None = Field(default=None, max_length=80)
    capabilities: list[str] | None = None
    expires_at: datetime | None = None


class PublicCredentialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    public_identifier: str
    credential_type: str
    display_name: str
    status: str
    environment: str
    policy_profile: str
    capabilities: list[str]
    created_by_user_id: str | None
    rotation_group_id: str | None
    parent_credential_id: str | None
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    rotated_at: datetime | None
    revoked_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    deleted_at: datetime | None
    origin_count: int = 0
    widget_configuration_status: str | None = None
    widget_configuration_version: int | None = None


class CredentialOriginCreate(BaseModel):
    origin: str = Field(min_length=1, max_length=512)
    wildcard_subdomains: bool = False


class CredentialOriginRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    credential_id: str
    scheme: str
    hostname: str
    port: int | None
    wildcard_subdomains: bool
    environment: str
    active: bool
    created_at: datetime
    updated_at: datetime


class WidgetConfigurationUpsert(BaseModel):
    bot_name: str | None = Field(default=None, max_length=120)
    welcome_message: str | None = Field(default=None, max_length=500)
    launcher_label: str | None = Field(default=None, max_length=80)
    primary_colour: str | None = Field(default=None, max_length=16)
    secondary_colour: str | None = Field(default=None, max_length=16)
    logo_path: str | None = Field(default=None, max_length=512)
    avatar_path: str | None = Field(default=None, max_length=512)
    position: str | None = Field(default=None, max_length=40)
    theme_mode: str | None = Field(default=None, max_length=40)
    suggested_questions_json: list[str] | None = None
    fallback_contact_text: str | None = Field(default=None, max_length=500)
    privacy_notice_text: str | None = Field(default=None, max_length=1000)
    privacy_notice_url: str | None = Field(default=None, max_length=512)
    terms_url: str | None = Field(default=None, max_length=512)
    language: str | None = Field(default=None, max_length=16)
    show_citations: bool | None = None
    allow_conversation_history: bool | None = None
    max_initial_suggestions: int | None = Field(default=None, ge=0, le=6)


class WidgetConfigurationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    credential_id: str
    status: str
    bot_name: str
    welcome_message: str
    launcher_label: str
    primary_colour: str
    secondary_colour: str | None
    logo_path: str | None
    avatar_path: str | None
    position: str
    theme_mode: str
    suggested_questions_json: list[str]
    fallback_contact_text: str | None
    privacy_notice_text: str | None
    privacy_notice_url: str | None
    terms_url: str | None
    language: str
    show_citations: bool
    allow_conversation_history: bool
    max_initial_suggestions: int
    configuration_version: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    safe_public_configuration: dict[str, Any] | None = None

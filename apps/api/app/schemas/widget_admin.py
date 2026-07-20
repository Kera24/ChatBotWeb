from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.public_access import WidgetConfigurationUpsert


class WidgetCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    environment: str = Field(default="development", max_length=40)
    initial_configuration: WidgetConfigurationUpsert | None = None


class WidgetDraftUpdateRequest(WidgetConfigurationUpsert):
    expected_concurrency_version: int = Field(ge=1)


class WidgetPublishRequest(BaseModel):
    draft_revision_id: str = Field(min_length=1, max_length=80)
    expected_concurrency_version: int = Field(ge=1)


class WidgetRollbackRequest(BaseModel):
    target_revision_id: str = Field(min_length=1, max_length=80)
    expected_active_revision_id: str = Field(min_length=1, max_length=80)


class WidgetValidationErrorItem(BaseModel):
    field: str
    code: str
    message: str


class WidgetConfigurationPayload(BaseModel):
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


class WidgetRevisionSummary(BaseModel):
    id: str
    revision_number: int
    status: str
    is_active_published: bool
    concurrency_version: int
    created_by_user_id: str | None
    created_at: datetime
    published_by_user_id: str | None
    published_at: datetime | None
    source_revision_id: str | None


class WidgetRevisionDetail(WidgetRevisionSummary):
    configuration: WidgetConfigurationPayload


class WidgetDraftRead(WidgetRevisionDetail):
    pass


class WidgetSummary(BaseModel):
    id: str
    display_name: str
    public_identifier: str
    public_credential_id: str
    publication_status: str
    active_revision_number: int | None
    active_published_revision_id: str | None
    draft_revision_id: str | None
    draft_dirty: bool
    operational_status: str
    pilot_status: str | None
    release_channel: str | None
    created_at: datetime
    updated_at: datetime


class WidgetDetail(WidgetSummary):
    draft: WidgetRevisionDetail | None = None
    active_published_revision: WidgetRevisionSummary | None = None
    diff: dict[str, Any] | None = None


class WidgetPublicationResult(BaseModel):
    widget: WidgetSummary
    published_revision: WidgetRevisionDetail
    validation_errors: list[WidgetValidationErrorItem] = []


class WidgetRollbackResult(WidgetPublicationResult):
    rolled_back_from_revision_id: str
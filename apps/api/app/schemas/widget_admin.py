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
    knowledge_scope_json: list[str] = []


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

class WidgetOriginCreateRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=512)


class WidgetOriginRead(BaseModel):
    id: str
    origin: str
    scheme: str
    hostname: str
    port: int | None
    wildcard_subdomains: bool
    environment: str
    active: bool
    created_at: datetime
    updated_at: datetime


class WidgetPublicKeyRotateRequest(BaseModel):
    expected_public_credential_id: str = Field(min_length=1, max_length=80)


class WidgetPublicKeyRotationResult(BaseModel):
    widget_id: str
    public_credential_id: str
    public_key: str
    public_key_status: str
    old_key_revoked: bool
    embed_update_required: bool
    rotated_at: datetime | None


class WidgetEmbedPreferenceUpdateRequest(BaseModel):
    version_mode: str = Field(max_length=40)
    pinned_sdk_version: str | None = Field(default=None, max_length=80)


class WidgetSupportedSdkVersion(BaseModel):
    version: str
    sdk_major: int
    protocol_major: int
    api_version: str
    support_status: str
    immutable_loader_path: str
    major_alias_path: str
    release_channel: str | None = None
    integrity: str | None = None


class WidgetSupportedSdkVersionsResponse(BaseModel):
    recommended: str
    versions: list[WidgetSupportedSdkVersion]


class WidgetEmbedMetadata(BaseModel):
    public_key: str
    public_key_status: str
    public_key_created_at: datetime
    public_key_rotated_at: datetime | None
    publication_status: str
    published: bool
    operational_status: str
    pilot_status: str
    release_channel: str
    version_mode: str
    pinned_sdk_version: str | None
    selected_sdk_version: str
    selected_loader_path: str
    protocol_major: int
    api_version: str
    sri: str | None
    snippet: str
    allowed_origins: list[WidgetOriginRead]
    active_published_revision_id: str | None
    active_revision_number: int | None
    readiness: list[str]
    active: bool
    embed_update_required: bool


class WidgetKnowledgeOption(BaseModel):
    id: str
    title: str
    type: str
    readiness: str
    indexing_status: str
    updated_at: datetime | None


class WidgetKnowledgeScopeUpdateRequest(BaseModel):
    document_ids: list[str] = []
    expected_concurrency_version: int = Field(ge=1)


class WidgetPublishValidationResult(BaseModel):
    publishable: bool
    errors: list[WidgetValidationErrorItem]
    warnings: list[WidgetValidationErrorItem]
    diff: dict[str, Any]
    knowledge: list[WidgetKnowledgeOption]


class WidgetPreviewGrantRequest(BaseModel):
    draft_revision_id: str = Field(min_length=1, max_length=80)


class WidgetPreviewGrantResult(BaseModel):
    preview_token: str
    expires_at: datetime
    draft_revision_id: str
    configuration: WidgetConfigurationPayload


class WidgetInstallationStatus(BaseModel):
    origin: str
    status: str
    last_seen_at: datetime | None
    sdk_version: str | None
    protocol_major: int | None
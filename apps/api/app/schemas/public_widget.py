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


class PublicWidgetConfigurationWidget(BaseModel):
    bot_name: str
    welcome_message: str
    launcher_label: str
    primary_colour: str
    secondary_colour: str | None = None
    logo_url: str | None = None
    avatar_url: str | None = None
    position: str
    theme_mode: str
    language: str


class PublicWidgetConfigurationBehaviour(BaseModel):
    suggested_questions: list[str]
    max_initial_suggestions: int
    show_citations: bool
    allow_conversation_history: bool
    session_required: bool
    messages_enabled: bool


class PublicWidgetConfigurationPrivacy(BaseModel):
    privacy_notice_text: str | None = None
    privacy_notice_url: str | None = None
    terms_url: str | None = None
    fallback_contact_text: str | None = None


class PublicWidgetConfigurationCapabilities(BaseModel):
    can_create_session: bool
    can_send_messages: bool
    citations_enabled: bool
    conversation_history_enabled: bool


class PublicWidgetConfigurationResponse(BaseModel):
    widget: PublicWidgetConfigurationWidget
    behaviour: PublicWidgetConfigurationBehaviour
    privacy: PublicWidgetConfigurationPrivacy
    capabilities: PublicWidgetConfigurationCapabilities
    configuration_version: int
    response_schema_version: str
    published_at: str
    request_id: str


class PublicWidgetErrorResponse(BaseModel):
    error: dict[str, object]

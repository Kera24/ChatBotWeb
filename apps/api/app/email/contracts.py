from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmailType(StrEnum):
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    # Reserved for future support (see the launch-readiness P0-2 task's
    # "Design for future support" list) - no template or call site exists
    # for these yet. Adding one is a new app.email.templates function plus a
    # new app.email.service wrapper, not a change to the provider
    # abstraction or any auth business logic.
    TEAM_INVITATION = "team_invitation"
    WELCOME = "welcome"
    BILLING_NOTIFICATION = "billing_notification"
    SECURITY_ALERT = "security_alert"
    WORKSPACE_INVITATION = "workspace_invitation"


class EmailMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    email_type: EmailType
    to_email: str
    subject: str
    html_body: str
    text_body: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailSendResult(BaseModel):
    provider_key: str
    email_type: EmailType
    success: bool
    latency_ms: int
    retry_count: int = 0
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

from fastapi import Request

from app.core.config import settings
from app.email.errors import EmailProviderConfigurationError
from app.email.providers.base import TransactionalEmailProvider
from app.email.providers.dev import DevEmailProvider
from app.email.providers.resend import ResendEmailProvider

# development/test: TRANSACTIONAL_EMAIL_PROVIDER left at its "dev" default is
# allowed - see _assert_dev_provider_allowed. Any other APP_ENV must
# configure a real provider; this mirrors the same "no silent mock/no-op
# fallback in production" policy app.ai.dependencies.create_ai_core applies
# to the AI generation provider (P0-1 of the launch-readiness review).
_NON_PRODUCTION_APP_ENVS = {"development", "test", "testing"}


def build_email_provider() -> TransactionalEmailProvider:
    """Called once at app startup (see app.main.create_app) - raises
    immediately rather than deferring a misconfiguration to the first
    password-reset/verification request."""
    provider_key = settings.TRANSACTIONAL_EMAIL_PROVIDER.strip().lower()
    if provider_key == "dev":
        _assert_dev_provider_allowed()
        return DevEmailProvider()
    if provider_key == "resend":
        return _build_resend_provider()
    raise EmailProviderConfigurationError(
        f"Unsupported TRANSACTIONAL_EMAIL_PROVIDER {settings.TRANSACTIONAL_EMAIL_PROVIDER!r}. "
        "Supported values: 'dev', 'resend'."
    )


def _assert_dev_provider_allowed() -> None:
    if settings.APP_ENV.strip().lower() in _NON_PRODUCTION_APP_ENVS:
        return
    raise EmailProviderConfigurationError(
        f"TRANSACTIONAL_EMAIL_PROVIDER is 'dev' (the default) but APP_ENV={settings.APP_ENV!r} is not a "
        "development/test environment. Refusing to silently no-op transactional email delivery outside "
        "development/test - set TRANSACTIONAL_EMAIL_PROVIDER=resend and the required RESEND_API_KEY/"
        "EMAIL_FROM_ADDRESS settings to configure real delivery."
    )


def _build_resend_provider() -> ResendEmailProvider:
    if not settings.RESEND_API_KEY:
        raise EmailProviderConfigurationError("TRANSACTIONAL_EMAIL_PROVIDER=resend requires RESEND_API_KEY to be set.")
    if not settings.EMAIL_FROM_ADDRESS:
        raise EmailProviderConfigurationError("TRANSACTIONAL_EMAIL_PROVIDER=resend requires EMAIL_FROM_ADDRESS to be set.")
    return ResendEmailProvider(
        api_key=settings.RESEND_API_KEY,
        from_address=settings.EMAIL_FROM_ADDRESS,
        from_name=settings.EMAIL_FROM_NAME,
    )


def get_email_provider(request: Request) -> TransactionalEmailProvider:
    return request.app.state.email_provider

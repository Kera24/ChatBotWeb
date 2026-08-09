"""Auth-facing email orchestration. Auth business logic (app.auth.service)
never imports a concrete provider - callers (app.api.v1.auth) pass in
whichever TransactionalEmailProvider app.email.dependencies.build_email_provider
selected, and this module is the only place that knows how to turn a
password-reset/verification token into an actual EmailMessage."""

import logging
from time import perf_counter

from app.core.config import settings
from app.email.contracts import EmailMessage, EmailSendResult, EmailType
from app.email.errors import EmailProviderError
from app.email.providers.base import TransactionalEmailProvider
from app.email.templates import render_password_reset_email, render_verification_email
from app.observability import otel_metrics
from app.operations.logging import log_operational_event, pseudonymous_identifier

logger = logging.getLogger("app.email.service")


def send_password_reset_email(provider: TransactionalEmailProvider, *, to_email: str, reset_token: str) -> EmailSendResult | None:
    reset_url = f"{settings.WEB_ORIGIN.rstrip('/')}/reset-password?token={reset_token}"
    subject, html_body, text_body = render_password_reset_email(
        reset_url=reset_url, expires_minutes=settings.AUTH_PASSWORD_RESET_MINUTES
    )
    return _send(
        provider,
        EmailMessage(email_type=EmailType.PASSWORD_RESET, to_email=to_email, subject=subject, html_body=html_body, text_body=text_body),
    )


def send_verification_email(provider: TransactionalEmailProvider, *, to_email: str, verification_token: str) -> EmailSendResult | None:
    verify_url = f"{settings.WEB_ORIGIN.rstrip('/')}/verify-email?token={verification_token}"
    subject, html_body, text_body = render_verification_email(
        verify_url=verify_url, expires_minutes=settings.AUTH_EMAIL_VERIFICATION_MINUTES
    )
    return _send(
        provider,
        EmailMessage(email_type=EmailType.EMAIL_VERIFICATION, to_email=to_email, subject=subject, html_body=html_body, text_body=text_body),
    )


def _send(provider: TransactionalEmailProvider, message: EmailMessage) -> EmailSendResult | None:
    """Fail-safe by design: a transactional-email failure must never break
    the auth flow it's attached to - the token/account state this is called
    after has already been committed, so a delivery failure here is a
    notification problem, not a reason to fail the request or reveal
    anything about account existence to the caller (see
    app.observability.ai_trace_recorder for the same "wrap in try/except,
    never break the primary path" pattern elsewhere in this codebase).

    Observability records provider/email_type/latency/success/retry_count/a
    safe error code only - never the message body, a token, or the API key
    (see SENSITIVE_FIELD_NAMES in app.operations.logging, which this reuses
    via log_operational_event; the recipient address is pseudonymised, never
    logged raw)."""
    started_at = perf_counter()
    try:
        result = provider.send(message)
    except EmailProviderError as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        log_operational_event(
            logger,
            {
                "event": "email.send_failed",
                "provider": provider.provider_key,
                "email_type": message.email_type.value,
                "success": False,
                "latency_ms": latency_ms,
                "retry_count": 0,
                "error_code": exc.code,
                "to": pseudonymous_identifier(message.to_email, prefix="email"),
            },
        )
        otel_metrics.record_email_delivery(provider=provider.provider_key, email_type=message.email_type.value, success=False, error_code=exc.code)
        return None

    log_operational_event(
        logger,
        {
            "event": "email.send",
            "provider": result.provider_key,
            "email_type": result.email_type.value,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "retry_count": result.retry_count,
            "to": pseudonymous_identifier(message.to_email, prefix="email"),
        },
    )
    otel_metrics.record_email_delivery(provider=result.provider_key, email_type=result.email_type.value, success=result.success, error_code=result.error_code)
    return result

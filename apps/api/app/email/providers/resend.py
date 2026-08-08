from time import perf_counter

import resend as resend_sdk

from app.email.contracts import EmailMessage, EmailSendResult
from app.email.errors import (
    EmailProviderAuthenticationError,
    EmailProviderConfigurationError,
    EmailProviderError,
    EmailProviderInvalidRequestError,
    EmailProviderRateLimitedError,
    EmailProviderUnavailableError,
)
from app.email.providers.base import TransactionalEmailProvider


class ResendEmailProvider(TransactionalEmailProvider):
    """Real transactional email delivery via the official `resend` Python
    SDK. Deliberately has NO fallback to a no-op/dev send on failure - send()
    always raises a classified EmailProviderError with an actionable message
    rather than silently degrading, matching the same "no silent fallback"
    guarantee OpenRouterAIProvider/OllamaEmbeddingProvider already establish
    elsewhere in this codebase (see app.ai.providers.openrouter,
    app.services.embeddings)."""

    provider_key = "resend"

    def __init__(self, *, api_key: str, from_address: str, from_name: str) -> None:
        if not api_key:
            raise EmailProviderConfigurationError(
                "ResendEmailProvider requires a non-empty api_key. Set RESEND_API_KEY."
            )
        if not from_address:
            raise EmailProviderConfigurationError(
                "ResendEmailProvider requires a non-empty from_address. Set EMAIL_FROM_ADDRESS."
            )
        self._api_key = api_key
        self.from_address = from_address
        self.from_name = from_name

    def send(self, message: EmailMessage) -> EmailSendResult:
        # The Resend SDK reads its API key from the module-level
        # `resend.api_key` global rather than accepting one per call - set it
        # immediately before every send (never logged, never included in any
        # exception message below) so this provider instance's own key is
        # always the one used, regardless of what else may have touched the
        # global in-process.
        resend_sdk.api_key = self._api_key
        started_at = perf_counter()
        sender = f"{self.from_name} <{self.from_address}>" if self.from_name else self.from_address
        try:
            response = resend_sdk.Emails.send(
                {
                    "from": sender,
                    "to": [message.to_email],
                    "subject": message.subject,
                    "html": message.html_body,
                    "text": message.text_body,
                }
            )
        except resend_sdk.exceptions.RateLimitError as exc:
            raise EmailProviderRateLimitedError(f"Resend rate limit exceeded: {exc.message}") from exc
        except (resend_sdk.exceptions.InvalidApiKeyError, resend_sdk.exceptions.MissingApiKeyError) as exc:
            raise EmailProviderAuthenticationError(f"Resend rejected the configured API key: {exc.message}") from exc
        except (
            resend_sdk.exceptions.ValidationError,
            resend_sdk.exceptions.MissingRequiredFieldsError,
            resend_sdk.exceptions.NoContentError,
        ) as exc:
            raise EmailProviderInvalidRequestError(f"Resend rejected the request as malformed: {exc.message}") from exc
        except resend_sdk.exceptions.ApplicationError as exc:
            raise EmailProviderUnavailableError(f"Resend returned an application/server error: {exc.message}") from exc
        except resend_sdk.exceptions.ResendError as exc:
            raise EmailProviderError(f"Resend returned an unclassified error (code={exc.code}): {exc.message}") from exc
        except Exception as exc:
            # Network-level failures (timeouts, DNS, connection resets)
            # surface as generic exceptions from the SDK's underlying HTTP
            # client, not a ResendError subclass - treat any of these as
            # "provider unavailable" rather than letting them propagate raw.
            raise EmailProviderUnavailableError(f"Could not reach Resend: {exc}") from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        message_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
        return EmailSendResult(
            provider_key=self.provider_key,
            email_type=message.email_type,
            success=True,
            latency_ms=latency_ms,
            retry_count=0,
            provider_message_id=message_id,
        )

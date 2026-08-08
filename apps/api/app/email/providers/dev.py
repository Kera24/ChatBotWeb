import logging
from time import perf_counter

from app.email.contracts import EmailMessage, EmailSendResult
from app.email.providers.base import TransactionalEmailProvider
from app.operations.logging import log_operational_event, pseudonymous_identifier

logger = logging.getLogger("app.email.providers.dev")


class DevEmailProvider(TransactionalEmailProvider):
    """Never makes a network call and never sends a real email - this is the
    development/test default (see app.email.dependencies.build_email_provider,
    which refuses to select this provider outside development/test). Logs
    that a send would have happened, using only safe fields (provider,
    email_type, a pseudonymous recipient identifier), so the flow stays
    observable locally without any risk of an accidental real send."""

    provider_key = "dev"

    def send(self, message: EmailMessage) -> EmailSendResult:
        started_at = perf_counter()
        log_operational_event(
            logger,
            {
                "event": "email.dev_provider.simulated_send",
                "provider": self.provider_key,
                "email_type": message.email_type.value,
                "to": pseudonymous_identifier(message.to_email, prefix="email"),
            },
        )
        digest = pseudonymous_identifier(f"{message.to_email}:{message.subject}", prefix="dev-msg")
        return EmailSendResult(
            provider_key=self.provider_key,
            email_type=message.email_type,
            success=True,
            latency_ms=int((perf_counter() - started_at) * 1000),
            retry_count=0,
            provider_message_id=digest,
        )

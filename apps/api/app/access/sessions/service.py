from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.access.credentials.contracts import CredentialRecord
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.sessions import repository
from app.access.sessions.contracts import (
    ConsumedMessageSlot,
    CreatePublicSessionCommand,
    CreatedPublicSession,
    SessionOperationResult,
    ValidatePublicSessionCommand,
    ValidatedPublicSessionContext,
)
from app.access.sessions.errors import raise_session_error
from app.access.sessions.tokens import (
    generate_public_session_token,
    hash_canonical_origin,
    hash_public_session_secret,
    parse_public_session_token,
    safe_token_id_fingerprint,
    verify_public_session_secret,
)
from app.core.config import settings
from app.db.models import PublicSession

Clock = Callable[[], datetime]

def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
CredentialLookup = Callable[[str], CredentialRecord | None]
ActiveCheck = Callable[[str], bool]
PolicyRequiresOrigin = Callable[[str], bool]


@dataclass(frozen=True)
class PublicSessionChecks:
    organisation_is_active: ActiveCheck
    workspace_is_active: ActiveCheck
    credential_lookup: CredentialLookup
    policy_requires_origin: PolicyRequiresOrigin = lambda policy_profile: policy_profile == "widget"


class PublicSessionService:
    def __init__(
        self,
        *,
        db: Session,
        checks: PublicSessionChecks,
        event_sink: InMemoryAccessEventSink | None = None,
        clock: Clock | None = None,
        token_hash_secret: str = settings.PUBLIC_SESSION_TOKEN_HASH_SECRET,
        token_version: str = settings.PUBLIC_SESSION_TOKEN_VERSION,
        token_id_bytes: int = settings.PUBLIC_SESSION_TOKEN_ID_BYTES,
        secret_bytes: int = settings.PUBLIC_SESSION_SECRET_BYTES,
    ) -> None:
        self.db = db
        self.checks = checks
        self.event_sink = event_sink
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.token_hash_secret = token_hash_secret
        self.token_version = token_version
        self.token_id_bytes = token_id_bytes
        self.secret_bytes = secret_bytes

    def create_session(self, command: CreatePublicSessionCommand) -> CreatedPublicSession:
        now = command.received_at or self.clock()
        self._verify_tenant_and_credential(
            organisation_id=command.organisation_id,
            workspace_id=command.workspace_id,
            credential_id=command.credential_id,
            channel=command.channel,
            environment=command.environment,
        )
        if self.checks.policy_requires_origin(command.policy_profile) and not command.canonical_origin:
            self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "session_origin_mismatch")
            raise_session_error("session_origin_mismatch")
        canonical_origin_hash = None
        if command.canonical_origin:
            canonical_origin_hash = hash_canonical_origin(canonical_origin=command.canonical_origin, hash_secret=self.token_hash_secret, version=self.token_version)
        expires_at = now + timedelta(seconds=command.inactivity_timeout_seconds)
        absolute_expires_at = now + timedelta(seconds=command.absolute_lifetime_seconds)
        if expires_at > absolute_expires_at:
            expires_at = absolute_expires_at
        for _attempt in range(5):
            generated = generate_public_session_token(environment=command.environment, token_id_bytes=self.token_id_bytes, secret_bytes=self.secret_bytes)
            token_secret_hash = hash_public_session_secret(
                token_id=generated.token_id,
                secret=generated.secret,
                hash_secret=self.token_hash_secret,
                version=self.token_version,
            )
            session = PublicSession(
                organisation_id=command.organisation_id,
                workspace_id=command.workspace_id,
                credential_id=command.credential_id,
                channel=command.channel,
                environment=command.environment,
                public_token_id=generated.token_id,
                token_secret_hash=token_secret_hash,
                token_hash_version=self.token_version,
                status="active",
                policy_profile=command.policy_profile,
                origin_id=command.origin_id,
                canonical_origin_hash=canonical_origin_hash,
                anonymous_user_id=None,
                message_count=0,
                last_activity_at=now,
                expires_at=expires_at,
                absolute_expires_at=absolute_expires_at,
                metadata_json=dict(command.metadata),
            )
            try:
                repository.create_session(self.db, session)
                self._emit("public_session.created", command.request_id, command.trace_id, command.channel, command.credential_id, "created", None)
                return CreatedPublicSession(
                    public_session_token=generated.token,
                    expires_at=expires_at,
                    absolute_expires_at=absolute_expires_at,
                    inactivity_timeout_seconds=command.inactivity_timeout_seconds,
                    max_messages=command.max_messages,
                    safe_capabilities=("message",),
                    request_id=command.request_id,
                    trace_id=command.trace_id,
                )
            except repository.PublicSessionTokenCollisionError:
                continue
        self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "temporarily_unavailable")
        raise_session_error("temporarily_unavailable")

    def validate_session(self, command: ValidatePublicSessionCommand, *, max_messages: int, inactivity_timeout_seconds: int) -> ValidatedPublicSessionContext:
        try:
            parts = parse_public_session_token(command.public_session_token)
        except ValueError:
            self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "invalid_session")
            raise_session_error("invalid_session")
        if parts.environment != command.environment:
            self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "invalid_session")
            raise_session_error("invalid_session")
        session = repository.get_by_token_id_for_verification(self.db, public_token_id=parts.token_id)
        if session is None:
            self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "invalid_session")
            raise_session_error("invalid_session")
        if not verify_public_session_secret(token_id=parts.token_id, secret=parts.secret, stored_hash=session.token_secret_hash, hash_secret=self.token_hash_secret, version=session.token_hash_version):
            self._emit("public_session.rejected", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "invalid_session")
            raise_session_error("invalid_session")
        self._verify_session_binding(session, command)
        self._verify_lifecycle(session, command.received_at, request_id=command.request_id, trace_id=command.trace_id)
        self._verify_tenant_and_credential(
            organisation_id=command.organisation_id,
            workspace_id=command.workspace_id,
            credential_id=command.credential_id,
            channel=command.channel,
            environment=command.environment,
        )
        self._verify_origin(session, command)
        if session.message_count >= max_messages:
            self._emit("public_session.message_limit_reached", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "session_limit_reached")
            raise_session_error("session_limit_reached")
        absolute_expires_at = _as_aware(session.absolute_expires_at)
        new_expires_at = min(command.received_at + timedelta(seconds=inactivity_timeout_seconds), absolute_expires_at)
        repository.update_valid_activity(self.db, session, now=command.received_at, expires_at=new_expires_at)
        remaining = max(max_messages - session.message_count, 0)
        self._emit("public_session.validated", command.request_id, command.trace_id, command.channel, command.credential_id, "validated", None)
        return ValidatedPublicSessionContext(
            internal_session_id=session.id,
            organisation_id=session.organisation_id,
            workspace_id=session.workspace_id,
            credential_id=session.credential_id,
            channel=session.channel,
            environment=session.environment,
            policy_profile=session.policy_profile,
            conversation_id=session.conversation_id,
            message_count=session.message_count,
            remaining_messages=remaining,
            expires_at=new_expires_at,
            absolute_expires_at=absolute_expires_at,
            rate_limit_identity=safe_token_id_fingerprint(token_id=session.public_token_id, hash_secret=self.token_hash_secret),
            request_id=command.request_id,
            trace_id=command.trace_id,
        )

    def consume_message_slot(self, context: ValidatedPublicSessionContext, *, max_messages: int, inactivity_timeout_seconds: int) -> ConsumedMessageSlot:
        now = self.clock()
        new_expires_at = min(now + timedelta(seconds=inactivity_timeout_seconds), _as_aware(context.absolute_expires_at))
        session = repository.atomically_increment_message_count(
            self.db,
            organisation_id=context.organisation_id,
            workspace_id=context.workspace_id,
            session_id=context.internal_session_id,
            max_messages=max_messages,
            now=now,
            expires_at=new_expires_at,
        )
        if session is None:
            self._emit("public_session.message_limit_reached", context.request_id, context.trace_id, context.channel, context.credential_id, "rejected", "session_limit_reached")
            raise_session_error("session_limit_reached")
        remaining = max(max_messages - session.message_count, 0)
        return ConsumedMessageSlot(
            internal_session_id=session.id,
            message_count=session.message_count,
            remaining_messages=remaining,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )

    def attach_conversation(self, context: ValidatedPublicSessionContext, *, conversation_id: str) -> str:
        session = repository.attach_conversation_once(
            self.db,
            organisation_id=context.organisation_id,
            workspace_id=context.workspace_id,
            session_id=context.internal_session_id,
            conversation_id=conversation_id,
            now=self.clock(),
        )
        self._emit("public_session.conversation_attached", context.request_id, context.trace_id, context.channel, context.credential_id, "attached", None)
        return str(session.conversation_id)

    def complete_session(self, context: ValidatedPublicSessionContext) -> SessionOperationResult:
        return self._mark(context, "completed", "public_session.completed")

    def revoke_session(self, context: ValidatedPublicSessionContext) -> SessionOperationResult:
        return self._mark(context, "revoked", "public_session.revoked")

    def block_session(self, context: ValidatedPublicSessionContext) -> SessionOperationResult:
        return self._mark(context, "blocked", "public_session.blocked")

    def expire_stale_sessions_in_batches(self, *, limit: int = 500) -> int:
        return repository.mark_expired_before(self.db, now=self.clock(), limit=limit)

    def _mark(self, context: ValidatedPublicSessionContext, status: str, event_type: str) -> SessionOperationResult:
        session = repository.mark_status(
            self.db,
            organisation_id=context.organisation_id,
            workspace_id=context.workspace_id,
            session_id=context.internal_session_id,
            status=status,
            now=self.clock(),
        )
        current_status = session.status if session is not None else status
        self._emit(event_type, context.request_id, context.trace_id, context.channel, context.credential_id, current_status, None)
        return SessionOperationResult(context.internal_session_id, current_status, context.request_id, context.trace_id)

    def _verify_session_binding(self, session: PublicSession, command: ValidatePublicSessionCommand) -> None:
        if session.organisation_id != command.organisation_id or session.workspace_id != command.workspace_id:
            raise_session_error("invalid_session")
        if session.credential_id != command.credential_id:
            raise_session_error("session_credential_mismatch")
        if session.channel != command.channel or session.environment != command.environment:
            raise_session_error("session_channel_mismatch")
        if session.policy_profile != command.policy_profile:
            raise_session_error("invalid_session")

    def _verify_lifecycle(self, session: PublicSession, now: datetime, *, request_id: str, trace_id: str) -> None:
        if session.status == "completed":
            raise_session_error("completed_session")
        if session.status == "revoked":
            raise_session_error("revoked_session")
        if session.status == "blocked":
            raise_session_error("blocked_session")
        if session.status == "expired":
            raise_session_error("expired_session")
        if session.status != "active":
            raise_session_error("invalid_session")
        expires_at = _as_aware(session.expires_at)
        absolute_expires_at = _as_aware(session.absolute_expires_at)
        if expires_at <= now or absolute_expires_at <= now:
            repository.mark_status(self.db, organisation_id=session.organisation_id, workspace_id=session.workspace_id, session_id=session.id, status="expired", now=now)
            self._emit("public_session.expired", request_id, trace_id, session.channel, session.credential_id, "expired", "expired_session")
            raise_session_error("expired_session")

    def _verify_origin(self, session: PublicSession, command: ValidatePublicSessionCommand) -> None:
        if session.canonical_origin_hash is None:
            if self.checks.policy_requires_origin(command.policy_profile):
                raise_session_error("session_origin_mismatch")
            return
        if command.canonical_origin is None:
            self._emit("public_session.origin_mismatch", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "session_origin_mismatch")
            raise_session_error("session_origin_mismatch")
        presented = hash_canonical_origin(canonical_origin=command.canonical_origin, hash_secret=self.token_hash_secret, version=session.token_hash_version)
        if presented != session.canonical_origin_hash:
            self._emit("public_session.origin_mismatch", command.request_id, command.trace_id, command.channel, command.credential_id, "rejected", "session_origin_mismatch")
            raise_session_error("session_origin_mismatch")

    def _verify_tenant_and_credential(self, *, organisation_id: str, workspace_id: str, credential_id: str, channel: str, environment: str) -> CredentialRecord:
        if not self.checks.organisation_is_active(organisation_id):
            raise_session_error("invalid_session")
        if not self.checks.workspace_is_active(workspace_id):
            raise_session_error("invalid_session")
        credential = self.checks.credential_lookup(credential_id)
        if credential is None or credential.organisation_id != organisation_id or credential.workspace_id != workspace_id:
            raise_session_error("invalid_session")
        if credential.status != "active" or credential.is_expired(self.clock()):
            self._emit("public_session.credential_invalidated", "unknown", "unknown", channel, credential_id, "rejected", "invalid_session")
            raise_session_error("invalid_session")
        if credential.environment != environment:
            raise_session_error("session_credential_mismatch")
        if channel == "widget" and credential.credential_type != "widget_public_key":
            raise_session_error("session_channel_mismatch")
        return credential

    def _emit(self, event_type: str, request_id: str, trace_id: str, channel: str | None, credential_id: str | None, outcome: str | None, error_code: str | None) -> None:
        if self.event_sink is None:
            return
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=request_id,
                trace_id=trace_id,
                channel=channel,
                credential_id=credential_id,
                outcome=outcome,
                error_code=error_code,
            )
        )


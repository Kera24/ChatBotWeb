from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.errors import PublicAccessError, raise_public_error
from app.access.messages.abuse.contracts import AbuseCheckRequest, AbuseDecision
from app.access.messages.abuse.service import PublicMessageAbuseService
from app.access.messages.contracts import PreparedPublicMessage
from app.access.messages.cost_control.contracts import PublicCostControlRequest, PublicCostDecision, PublicCostPolicy
from app.access.messages.cost_control.policies import conservative_restricted_policy, public_cost_policy_from_access_policy
from app.access.messages.cost_control.service import PublicMessageCostControlService, estimate_tokens
from app.access.messages.idempotency import PublicMessageIdempotencyService
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.policies.models import AccessPolicyProfile
from app.access.sessions.contracts import ValidatedPublicSessionContext
from app.access.sessions.service import PublicSessionService
from app.core.config import settings
from app.db.models import PublicMessageRequest, PublicSession

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SecuredPublicMessage:
    prepared: PreparedPublicMessage
    abuse_decision: AbuseDecision
    cost_decision: PublicCostDecision
    effective_retrieval_limit: int
    effective_max_context_characters: int
    effective_max_output_tokens: int
    provider_timeout_seconds: int
    safe_restriction_flags: tuple[str, ...]
    request_id: str
    trace_id: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cost_decision"] = self.cost_decision.to_dict()
        return data


class PublicMessageSecurityService:
    def __init__(
        self,
        *,
        db: Session,
        abuse_service: PublicMessageAbuseService,
        cost_control_service: PublicMessageCostControlService,
        idempotency_service: PublicMessageIdempotencyService,
        public_session_service: PublicSessionService | None = None,
        event_sink: InMemoryAccessEventSink | None = None,
        clock: Clock = _utc_now,
    ) -> None:
        self.db = db
        self.abuse_service = abuse_service
        self.cost_control_service = cost_control_service
        self.idempotency_service = idempotency_service
        self.public_session_service = public_session_service
        self.event_sink = event_sink or InMemoryAccessEventSink()
        self.clock = clock

    def secure(self, prepared: PreparedPublicMessage, *, access_policy: AccessPolicyProfile) -> SecuredPublicMessage:
        self._emit("widget.message.abuse_check_started", prepared, outcome="started")
        try:
            message_hash = prepared.request_hash
            abuse_request = AbuseCheckRequest(
                organisation_id=prepared.organisation_id,
                workspace_id=prepared.workspace_id,
                credential_id=prepared.credential_id,
                public_session_id=prepared.public_session_id,
                conversation_id=prepared.conversation_id,
                canonical_message=prepared.canonical_message,
                message_hash=message_hash,
                policy_profile=prepared.policy_profile,
                channel=prepared.channel,
                recent_session_message_fingerprints=self._recent_fingerprints(prepared),
                request_id=prepared.request_id,
                trace_id=prepared.trace_id,
                received_at=self.clock(),
            )
            abuse_decision = self.abuse_service.evaluate(abuse_request)
            if abuse_decision.status == "block_session":
                self._block_session(prepared)
                self._mark_failed(prepared, "unsafe_request")
                self._emit("widget.message.session_blocked", prepared, outcome="blocked", error_code="unsafe_request")
                raise_public_error("unsafe_request")
            if abuse_decision.status == "reject":
                self._mark_failed(prepared, abuse_decision.safe_public_error_code or "unsafe_request")
                self._emit("widget.message.abuse_rejected", prepared, outcome="rejected", error_code="unsafe_request")
                raise_public_error("unsafe_request")
            if abuse_decision.status == "allow_with_restrictions":
                self._emit("widget.message.abuse_restricted", prepared, outcome="restricted")
            else:
                self._emit("widget.message.abuse_allowed", prepared, outcome="allowed")

            self._emit("widget.message.cost_check_started", prepared, outcome="started")
            base_policy = public_cost_policy_from_access_policy(access_policy)
            effective_policy = conservative_restricted_policy(base_policy) if abuse_decision.status == "allow_with_restrictions" else base_policy
            input_tokens = estimate_tokens(prepared.canonical_message)
            cost_request = PublicCostControlRequest(
                organisation_id=prepared.organisation_id,
                workspace_id=prepared.workspace_id,
                credential_id=prepared.credential_id,
                public_session_id=prepared.public_session_id,
                policy_profile=prepared.policy_profile,
                canonical_message=prepared.canonical_message,
                message_character_count=len(prepared.canonical_message),
                estimated_input_tokens=input_tokens,
                requested_operation="public_widget_message",
                current_session_message_count=self._session_message_count(prepared),
                current_daily_message_count=None,
                current_daily_token_usage=None,
                current_daily_estimated_cost=None,
                request_id=prepared.request_id,
                trace_id=prepared.trace_id,
                received_at=self.clock(),
            )
            cost_decision = self.cost_control_service.evaluate(cost_request, policy=effective_policy)
            if not cost_decision.allowed:
                safe_error = "quota_exceeded" if cost_decision.reason_code.endswith("quota_exceeded") or cost_decision.reason_code.endswith("budget_exceeded") else "temporarily_unavailable"
                self._mark_failed(prepared, safe_error)
                event_type = "widget.message.quota_denied" if safe_error == "quota_exceeded" else "widget.message.cost_policy_invalid"
                self._emit(event_type, prepared, outcome="rejected", error_code=safe_error)
                raise_public_error(safe_error)
            self._emit("widget.message.cost_allowed", prepared, outcome="allowed")
            secured = SecuredPublicMessage(
                prepared=prepared,
                abuse_decision=abuse_decision,
                cost_decision=cost_decision,
                effective_retrieval_limit=cost_decision.retrieval_limit,
                effective_max_context_characters=cost_decision.max_context_characters,
                effective_max_output_tokens=cost_decision.max_output_tokens,
                provider_timeout_seconds=cost_decision.provider_timeout_seconds,
                safe_restriction_flags=(abuse_decision.restriction_profile,) if abuse_decision.restriction_profile else (),
                request_id=prepared.request_id,
                trace_id=prepared.trace_id,
            )
            self._emit("widget.message.security_preparation_completed", prepared, outcome="completed")
            return secured
        except PublicAccessError:
            self._emit("widget.message.security_preparation_failed", prepared, outcome="failed")
            raise
        except Exception:
            self._mark_failed(prepared, "safe_internal_error")
            self._emit("widget.message.security_preparation_failed", prepared, outcome="failed", error_code="safe_internal_error")
            raise_public_error("safe_internal_error")

    def _recent_fingerprints(self, prepared: PreparedPublicMessage) -> tuple[str, ...]:
        lookback = settings.PUBLIC_MESSAGE_REPEATED_LOOKBACK_COUNT
        statement = (
            select(PublicMessageRequest.request_hash)
            .where(
                PublicMessageRequest.public_session_id == prepared.public_session_id,
                PublicMessageRequest.id != prepared.idempotency_record_id,
                PublicMessageRequest.deleted_at.is_(None),
            )
            .order_by(PublicMessageRequest.created_at.desc())
            .limit(lookback)
        )
        return tuple(str(row[0]) for row in self.db.execute(statement).all())

    def _session_message_count(self, prepared: PreparedPublicMessage) -> int:
        session = self.db.get(PublicSession, prepared.public_session_id)
        return int(session.message_count) if session is not None else 0

    def _mark_failed(self, prepared: PreparedPublicMessage, error_code: str) -> None:
        self.idempotency_service.mark_failed(
            record_id=prepared.idempotency_record_id,
            organisation_id=prepared.organisation_id,
            workspace_id=prepared.workspace_id,
            error_code=error_code,
            now=self.clock(),
        )

    def _block_session(self, prepared: PreparedPublicMessage) -> None:
        if self.public_session_service is None:
            return
        session = self.db.get(PublicSession, prepared.public_session_id)
        if session is None:
            return
        context = ValidatedPublicSessionContext(
            internal_session_id=session.id,
            organisation_id=session.organisation_id,
            workspace_id=session.workspace_id,
            credential_id=session.credential_id,
            channel=session.channel,
            environment=session.environment,
            policy_profile=session.policy_profile,
            conversation_id=session.conversation_id,
            message_count=session.message_count,
            remaining_messages=0,
            expires_at=session.expires_at,
            absolute_expires_at=session.absolute_expires_at,
            rate_limit_identity=f"public_session:{session.id}",
            request_id=prepared.request_id,
            trace_id=prepared.trace_id,
        )
        self.public_session_service.block_session(context)

    def _emit(self, event_type: str, prepared: PreparedPublicMessage, *, outcome: str, error_code: str | None = None) -> None:
        self.event_sink.emit(
            AccessEvent(
                event_type=event_type,
                request_id=prepared.request_id,
                trace_id=prepared.trace_id,
                channel=prepared.channel,
                credential_id=prepared.credential_id,
                outcome=outcome,
                error_code=error_code,
            )
        )


def safe_message_fingerprint(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()

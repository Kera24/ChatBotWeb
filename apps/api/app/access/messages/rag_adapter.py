from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from app.access.errors import raise_public_error
from app.access.messages.idempotency import PublicMessageIdempotencyService
from app.access.messages.output import PublicOutputSanitisationRequest, PublicOutputSanitiser
from app.access.messages.security import SecuredPublicMessage
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink
from app.access.widget_config.repository import get_configuration_for_credential
from app.ai.rag_orchestrator import RAGOrchestrationRequest, RAGOrchestrator, RAGOrchestratorError, RAGProviderExecutionError

_RESPONSE_SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class PublicRAGAdapterResult:
    public_response: dict[str, Any]
    user_message_id: str
    assistant_message_id: str
    execution_id: str
    fallback_used: bool
    internal_metadata: dict[str, Any] = field(default_factory=dict)


class PublicWidgetRAGAdapter:
    def __init__(
        self,
        *,
        orchestrator: RAGOrchestrator,
        idempotency_service: PublicMessageIdempotencyService,
        event_sink: InMemoryAccessEventSink | None = None,
        output_sanitiser: PublicOutputSanitiser | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.idempotency_service = idempotency_service
        self.event_sink = event_sink
        self.output_sanitiser = output_sanitiser or PublicOutputSanitiser()

    def execute(self, secured: SecuredPublicMessage) -> PublicRAGAdapterResult:
        prepared = secured.prepared
        self._emit("widget.message.rag_started", secured, outcome="started")
        try:
            result = self.orchestrator.answer(
                RAGOrchestrationRequest(
                    organisation_id=prepared.organisation_id,
                    workspace_id=prepared.workspace_id,
                    conversation_id=prepared.conversation_id,
                    query=prepared.canonical_message,
                    channel="widget",
                    model_key=None,
                    prompt_key=None,
                    retrieval_limit=secured.effective_retrieval_limit,
                    max_context_chars=secured.effective_max_context_characters,
                    metadata={
                        "public_access": True,
                        "knowledge_document_ids": _knowledge_scope_for(self.orchestrator.db, prepared),
                        "public_session_id": prepared.public_session_id,
                        "idempotency_record_id": prepared.idempotency_record_id,
                    },
                )
            )
        except RAGProviderExecutionError:
            self._mark_failed(prepared, "temporarily_unavailable")
            self._emit("widget.message.rag_failed", secured, outcome="failed", error_code="temporarily_unavailable")
            raise_public_error("temporarily_unavailable")
        except RAGOrchestratorError:
            self._mark_failed(prepared, "temporarily_unavailable")
            self._emit("widget.message.rag_failed", secured, outcome="failed", error_code="temporarily_unavailable")
            raise_public_error("temporarily_unavailable")

        self._emit("widget.message.rag_completed", secured, outcome="completed")
        sanitised = self._sanitise_result(secured, result)
        public_response = {
            "response_id": _public_response_id(result.assistant_message_id, prepared.request_id),
            "answer": sanitised.safe_answer,
            "answer_state": sanitised.answer_state,
            "citations": [citation.to_dict() for citation in sanitised.safe_citations],
            "remaining_messages": prepared.remaining_messages,
            "fallback_used": sanitised.fallback_replaced or result.fallback_used or sanitised.answer_state == "fallback",
            "request_id": prepared.request_id,
            "response_schema_version": _RESPONSE_SCHEMA_VERSION,
        }
        self.idempotency_service.mark_completed(
            record_id=prepared.idempotency_record_id,
            organisation_id=prepared.organisation_id,
            workspace_id=prepared.workspace_id,
            response_snapshot=public_response,
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
        )
        return PublicRAGAdapterResult(
            public_response=public_response,
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            execution_id=result.execution_id,
            fallback_used=public_response["fallback_used"] is True,
            internal_metadata={
                "answer_state": sanitised.answer_state,
                "retrieved_chunk_count": result.retrieved_chunk_count,
                "token_total": result.token_usage.total_tokens,
                "estimated_cost": str(result.estimated_cost),
                "sanitiser_version": sanitised.decision_version,
                "sanitisation_applied": sanitised.sanitisation_applied,
            },
        )

    def _sanitise_result(self, secured: SecuredPublicMessage, result):  # noqa: ANN001
        prepared = secured.prepared
        self._emit("widget.message.output_sanitisation_started", secured, outcome="started")
        try:
            sanitised = self.output_sanitiser.sanitise(
                PublicOutputSanitisationRequest(
                    answer=result.answer,
                    answer_state=result.answer_state,
                    authorised_citations=result.citations,
                    fallback_used=result.fallback_used,
                    policy_profile=prepared.policy_profile,
                    request_id=prepared.request_id,
                    trace_id=prepared.trace_id,
                    known_internal_values=tuple(
                        str(value)
                        for value in (
                            prepared.organisation_id,
                            prepared.workspace_id,
                            prepared.credential_id,
                            prepared.public_session_id,
                            prepared.conversation_id,
                            prepared.idempotency_record_id,
                            result.user_message_id,
                            result.assistant_message_id,
                            result.execution_id,
                            result.provider_key,
                            result.model_key,
                            result.provider_model_name,
                            result.prompt_key,
                            result.prompt_version,
                            result.prompt_hash,
                        )
                        if value
                    ),
                    internal_metadata={"execution_id": result.execution_id},
                )
            )
        except Exception:
            self._emit("widget.message.output_sanitisation_failed", secured, outcome="failed", error_code="safe_internal_error")
            raise_public_error("safe_internal_error")
        if sanitised.sanitisation_applied:
            self._emit("widget.message.output_sanitised", secured, outcome="sanitised")
        if "truncated" in sanitised.removed_content_categories:
            self._emit("widget.message.output_truncated", secured, outcome="truncated")
        if "unsafe_link" in sanitised.removed_content_categories:
            self._emit("widget.message.unsafe_link_removed", secured, outcome="removed")
        if sanitised.citation_validation_result.removed_count:
            self._emit("widget.message.citation_removed", secured, outcome="removed")
        if sanitised.citation_validation_result.marker_rewritten:
            self._emit("widget.message.citation_marker_rewritten", secured, outcome="rewritten")
        if sanitised.leakage_detected:
            self._emit("widget.message.internal_leakage_detected", secured, outcome="detected")
        if "system_prompt_leakage" in sanitised.removed_content_categories:
            self._emit("widget.message.system_prompt_leakage_detected", secured, outcome="detected")
        if sanitised.fallback_replaced:
            self._emit("widget.message.output_replaced_with_fallback", secured, outcome="fallback")
        return sanitised

    def _mark_failed(self, prepared, error_code: str) -> None:  # noqa: ANN001
        self.idempotency_service.mark_failed(
            record_id=prepared.idempotency_record_id,
            organisation_id=prepared.organisation_id,
            workspace_id=prepared.workspace_id,
            error_code=error_code,
        )

    def _emit(self, event_type: str, secured: SecuredPublicMessage, *, outcome: str, error_code: str | None = None) -> None:
        if self.event_sink is None:
            return
        prepared = secured.prepared
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


def _public_response_id(assistant_message_id: str, request_id: str) -> str:
    digest = sha256(f"{assistant_message_id}:{request_id}".encode("utf-8")).hexdigest()[:20]
    return f"pmr_{digest}"

def _knowledge_scope_for(db, prepared) -> list[str]:  # noqa: ANN001
    configuration = get_configuration_for_credential(
        db,
        organisation_id=prepared.organisation_id,
        workspace_id=prepared.workspace_id,
        credential_id=prepared.credential_id,
    )
    return list(getattr(configuration, "knowledge_scope_json", None) or [])
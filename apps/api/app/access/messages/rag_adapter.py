from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from app.ai.rag_orchestrator import RAGOrchestrationRequest, RAGOrchestrator, RAGOrchestratorError, RAGProviderExecutionError
from app.access.errors import raise_public_error
from app.access.messages.idempotency import PublicMessageIdempotencyService
from app.access.messages.security import SecuredPublicMessage
from app.access.observability.events import AccessEvent, InMemoryAccessEventSink

_RESPONSE_SCHEMA_VERSION = "1.0"
_MAX_ANSWER_CHARS = 4000
_MAX_CITATIONS = 5
_MAX_QUOTED_TEXT_CHARS = 500
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PublicRAGCitation:
    citation_index: int
    source_title: str
    source_type: str
    page_number: int | None = None
    section_title: str | None = None
    quoted_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class PublicRAGAdapterResult:
    public_response: dict[str, Any]
    user_message_id: str
    assistant_message_id: str
    execution_id: str
    fallback_used: bool
    internal_metadata: dict[str, Any] = field(default_factory=dict)


class PublicWidgetRAGAdapter:
    def __init__(self, *, orchestrator: RAGOrchestrator, idempotency_service: PublicMessageIdempotencyService, event_sink: InMemoryAccessEventSink | None = None) -> None:
        self.orchestrator = orchestrator
        self.idempotency_service = idempotency_service
        self.event_sink = event_sink

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
        public_response = project_public_rag_response(
            answer=result.answer,
            answer_state=result.answer_state,
            citations=result.citations,
            remaining_messages=prepared.remaining_messages,
            fallback_used=result.fallback_used,
            request_id=prepared.request_id,
            response_id=_public_response_id(result.assistant_message_id, prepared.request_id),
        )
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
            fallback_used=result.fallback_used,
            internal_metadata={
                "answer_state": result.answer_state,
                "retrieved_chunk_count": result.retrieved_chunk_count,
                "token_total": result.token_usage.total_tokens,
                "estimated_cost": str(result.estimated_cost),
            },
        )

    def _mark_failed(self, prepared, error_code: str) -> None:
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


def project_public_rag_response(*, answer: str, answer_state: str, citations: list[Any], remaining_messages: int, fallback_used: bool, request_id: str, response_id: str) -> dict[str, Any]:
    safe_answer = _plain_text(answer, max_chars=_MAX_ANSWER_CHARS)
    safe_state = _public_answer_state(answer_state, fallback_used=fallback_used)
    safe_citations = [] if fallback_used or safe_state in {"fallback", "temporarily_unavailable"} else project_public_citations(citations)
    return {
        "response_id": response_id,
        "answer": safe_answer,
        "answer_state": safe_state,
        "citations": [citation.to_dict() for citation in safe_citations],
        "remaining_messages": remaining_messages,
        "fallback_used": bool(fallback_used),
        "request_id": request_id,
        "response_schema_version": _RESPONSE_SCHEMA_VERSION,
    }


def project_public_citations(citations: list[Any]) -> list[PublicRAGCitation]:
    seen: set[tuple[object, ...]] = set()
    projected: list[PublicRAGCitation] = []
    for citation in sorted(citations, key=lambda item: getattr(item, "citation_index", 0)):
        key = (
            getattr(citation, "source_title", None),
            getattr(citation, "source_type", None),
            getattr(citation, "page_number", None),
            getattr(citation, "section_title", None),
            getattr(citation, "quoted_text", None),
        )
        if key in seen:
            continue
        seen.add(key)
        projected.append(
            PublicRAGCitation(
                citation_index=len(projected) + 1,
                source_title=_plain_text(str(getattr(citation, "source_title", "Source")), max_chars=200),
                source_type=_plain_text(str(getattr(citation, "source_type", "document")), max_chars=80),
                page_number=getattr(citation, "page_number", None),
                section_title=_plain_text(str(getattr(citation, "section_title")), max_chars=200) if getattr(citation, "section_title", None) else None,
                quoted_text=_plain_text(str(getattr(citation, "quoted_text")), max_chars=_MAX_QUOTED_TEXT_CHARS) if getattr(citation, "quoted_text", None) else None,
            )
        )
        if len(projected) >= _MAX_CITATIONS:
            break
    return projected


def _plain_text(value: str, *, max_chars: int) -> str:
    stripped = _TAG_RE.sub("", value)
    escaped = html.escape(stripped, quote=False)
    return escaped[:max_chars]


def _public_answer_state(answer_state: str, *, fallback_used: bool) -> str:
    if fallback_used or answer_state == "fallback":
        return "fallback"
    if answer_state == "low_confidence":
        return "low_confidence"
    if answer_state == "answered":
        return "answered"
    return "temporarily_unavailable"


def _public_response_id(assistant_message_id: str, request_id: str) -> str:
    digest = sha256(f"{assistant_message_id}:{request_id}".encode("utf-8")).hexdigest()[:20]
    return f"pmr_{digest}"

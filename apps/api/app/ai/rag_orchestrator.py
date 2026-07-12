from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.ai.accounting import AIUsageRecord
from app.ai.contracts import FinishReason, TokenUsage
from app.ai.dependencies import AICoreContainer
from app.ai.errors import AIProviderError
from app.ai.model_registry import ModelConfig
from app.ai.service import AICoreGenerateInput
from app.core.config import settings
from app.repositories import conversation_repository
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.services.conversation import (
    append_assistant_message,
    append_user_message,
    attach_citations_to_assistant_message,
    start_conversation,
)
from app.services.embeddings import EmbeddingProvider
from app.services.retrieval_context import RetrievalCitationData, assemble_retrieval_context


DEFAULT_RAG_PROMPT_KEY = "grounded_rag_answer"
DEFAULT_RAG_MODEL_KEY = "mock-grounded-answer"
FALLBACK_ANSWER = "The available knowledge base does not contain enough information to answer that."


class RAGOrchestratorError(Exception):
    code = "RAG_ORCHESTRATOR_ERROR"

    def __init__(self, message: str = "RAG orchestration failed.") -> None:
        super().__init__(message)
        self.message = message


class RAGTenantContextError(RAGOrchestratorError):
    code = "TENANT_CONTEXT_INVALID"


class RAGConversationNotFoundError(RAGOrchestratorError):
    code = "CONVERSATION_NOT_FOUND"


class RAGProviderExecutionError(RAGOrchestratorError):
    code = "RAG_PROVIDER_EXECUTION_FAILED"

    def __init__(self, message: str, *, provider_error_code: str, execution_id: str, assistant_message_id: str) -> None:
        super().__init__(message)
        self.provider_error_code = provider_error_code
        self.execution_id = execution_id
        self.assistant_message_id = assistant_message_id


@dataclass(frozen=True)
class RAGOrchestrationRequest:
    organisation_id: str
    workspace_id: str
    query: str
    channel: str = "dashboard_test"
    conversation_id: str | None = None
    model_key: str | None = None
    prompt_key: str | None = None
    retrieval_limit: int | None = None
    max_context_chars: int | None = None
    metadata: dict | None = None
    simulate_failure: bool = False
    simulate_timeout: bool = False


@dataclass(frozen=True)
class RAGCitationResult:
    citation_index: int
    chunk_id: str
    document_id: str
    document_version_id: str
    source_title: str
    source_type: str
    page_number: int | None
    section_title: str | None
    similarity_score: float | None
    quoted_text: str | None = None


@dataclass(frozen=True)
class RAGOrchestrationResult:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    answer: str
    answer_state: str
    citations: list[RAGCitationResult]
    retrieved_chunk_count: int
    provider_key: str
    model_key: str
    provider_model_name: str
    prompt_key: str
    prompt_version: str
    prompt_hash: str
    execution_id: str
    token_usage: TokenUsage
    estimated_cost: Decimal
    latency_ms: int
    finish_reason: FinishReason
    fallback_used: bool
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RAGOrchestratorDependencies:
    db: Session
    ai_core: AICoreContainer
    embedding_provider: EmbeddingProvider


class RAGOrchestrator:
    def __init__(self, dependencies: RAGOrchestratorDependencies) -> None:
        self.db = dependencies.db
        self.ai_core = dependencies.ai_core
        self.embedding_provider = dependencies.embedding_provider

    def answer(self, request: RAGOrchestrationRequest) -> RAGOrchestrationResult:
        self._validate_workspace(request)
        conversation = self._resolve_conversation(request)
        user_message = append_user_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            content=request.query,
            metadata_json=request.metadata,
        )

        retrieval_limit = request.retrieval_limit or settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
        max_context_chars = request.max_context_chars or settings.RETRIEVAL_MAX_CONTEXT_CHARS
        retrieval = assemble_retrieval_context(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            query=request.query,
            search_limit=retrieval_limit,
            max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
            max_context_chars=max_context_chars,
            provider=self.embedding_provider,
        )
        context = "\n\n".join(block.context_text for block in retrieval.context_blocks)
        model_key = request.model_key or DEFAULT_RAG_MODEL_KEY
        prompt_key = request.prompt_key or DEFAULT_RAG_PROMPT_KEY
        model = self.ai_core.model_registry.get(model_key, require_enabled=True)

        if not retrieval.context_blocks:
            return self._persist_fallback(
                request=request,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                model=model,
                prompt_key=prompt_key,
            )

        execution_id = self.ai_core.accounting_service.create_execution_id()
        try:
            ai_response = self.ai_core.service.generate(
                AICoreGenerateInput(
                    prompt_key=prompt_key,
                    model_key=model_key,
                    variables={"question": request.query, "context": context},
                    execution_id=execution_id,
                    organisation_id=request.organisation_id,
                    workspace_id=request.workspace_id,
                    simulate_failure=request.simulate_failure,
                    simulate_timeout=request.simulate_timeout,
                )
            )
        except AIProviderError as exc:
            record = self._find_usage_record(execution_id)
            assistant_message = append_assistant_message(
                self.db,
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                conversation_id=conversation.id,
                content="The assistant could not generate an answer because the AI provider failed.",
                answer_state="failed",
                model_key=model_key,
                provider_key=model.provider_key,
                provider_model_name=model.provider_model_name,
                prompt_key=prompt_key,
                prompt_version=record.prompt_version if record else None,
                prompt_hash=record.prompt_hash if record else None,
                execution_id=execution_id,
                input_tokens=record.prompt_tokens if record else None,
                output_tokens=record.completion_tokens if record else None,
                total_tokens=record.total_tokens if record else None,
                estimated_cost=record.total_estimated_cost if record else Decimal("0"),
                latency_ms=record.latency_ms if record else 0,
                finish_reason=(record.finish_reason.value if record else FinishReason.ERROR.value),
                error_code=exc.code,
                metadata_json={"provider_error_code": exc.code, "provider_error_message": exc.message},
            )
            raise RAGProviderExecutionError(
                "AI provider execution failed while preserving conversation state.",
                provider_error_code=exc.code,
                execution_id=execution_id,
                assistant_message_id=assistant_message.id,
            ) from exc

        record = self._find_usage_record(execution_id)
        estimated_cost = record.total_estimated_cost if record else Decimal("0")
        assistant_message = append_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            content=ai_response.text,
            answer_state="answered",
            model_key=ai_response.model_key,
            provider_key=ai_response.provider_key,
            provider_model_name=ai_response.provider_model_name,
            prompt_key=ai_response.prompt_key,
            prompt_version=_prompt_version_to_int(ai_response.prompt_version),
            prompt_hash=ai_response.prompt_hash,
            execution_id=execution_id,
            input_tokens=ai_response.token_usage.input_tokens,
            output_tokens=ai_response.token_usage.output_tokens,
            total_tokens=ai_response.token_usage.total_tokens,
            estimated_cost=estimated_cost,
            latency_ms=ai_response.latency_ms,
            finish_reason=ai_response.finish_reason.value,
            metadata_json={
                "prompt_version": ai_response.prompt_version,
                "provider_metadata": ai_response.provider_metadata.model_dump(mode="json"),
                "ai_response_metadata": ai_response.metadata,
                "retrieval": {
                    "requested_limit": retrieval_limit,
                    "returned_chunks": len(retrieval.context_blocks),
                    "total_context_chars": retrieval.total_context_chars,
                },
            },
        )
        citation_payloads = [_citation_payload(citation, block.content) for citation, block in zip(retrieval.citations, retrieval.context_blocks, strict=True)]
        persisted_citations = attach_citations_to_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            citations=citation_payloads,
        )
        return RAGOrchestrationResult(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=ai_response.text,
            answer_state="answered",
            citations=[
                RAGCitationResult(
                    citation_index=citation.citation_index,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    document_version_id=citation.document_version_id,
                    source_title=citation.source_title,
                    source_type=citation.source_type,
                    page_number=citation.page_number,
                    section_title=citation.section_title,
                    similarity_score=float(citation.similarity_score) if citation.similarity_score is not None else None,
                    quoted_text=citation.quoted_text,
                )
                for citation in persisted_citations
            ],
            retrieved_chunk_count=len(retrieval.context_blocks),
            provider_key=ai_response.provider_key,
            model_key=ai_response.model_key,
            provider_model_name=ai_response.provider_model_name,
            prompt_key=ai_response.prompt_key,
            prompt_version=ai_response.prompt_version,
            prompt_hash=ai_response.prompt_hash,
            execution_id=execution_id,
            token_usage=ai_response.token_usage,
            estimated_cost=estimated_cost,
            latency_ms=ai_response.latency_ms,
            finish_reason=ai_response.finish_reason,
            fallback_used=False,
            metadata={"total_context_chars": retrieval.total_context_chars},
        )

    def _validate_workspace(self, request: RAGOrchestrationRequest) -> None:
        workspace = get_workspace_for_organisation(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
        )
        if workspace is None:
            raise RAGTenantContextError("Workspace not found for organisation.")

    def _resolve_conversation(self, request: RAGOrchestrationRequest):
        if request.conversation_id is None:
            return start_conversation(
                self.db,
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                channel=request.channel,
                metadata_json=request.metadata,
            )
        conversation = conversation_repository.get_conversation(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=request.conversation_id,
        )
        if conversation is None:
            raise RAGConversationNotFoundError("Conversation not found for tenant workspace.")
        return conversation

    def _persist_fallback(
        self,
        *,
        request: RAGOrchestrationRequest,
        conversation_id: str,
        user_message_id: str,
        model: ModelConfig,
        prompt_key: str,
    ) -> RAGOrchestrationResult:
        prompt_version = self.ai_core.prompt_registry.resolve_active(prompt_key)
        execution_id = self.ai_core.accounting_service.create_execution_id()
        assistant_message = append_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation_id,
            content=FALLBACK_ANSWER,
            answer_state="fallback",
            model_key=model.model_key,
            provider_key=model.provider_key,
            provider_model_name=model.provider_model_name,
            prompt_key=prompt_key,
            prompt_version=_prompt_version_to_int(prompt_version.version),
            prompt_hash=prompt_version.prompt_hash,
            execution_id=execution_id,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            latency_ms=0,
            finish_reason=FinishReason.STOP.value,
            metadata_json={"fallback_reason": "retrieval_empty", "prompt_version": prompt_version.version},
        )
        return RAGOrchestrationResult(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            answer=FALLBACK_ANSWER,
            answer_state="fallback",
            citations=[],
            retrieved_chunk_count=0,
            provider_key=model.provider_key,
            model_key=model.model_key,
            provider_model_name=model.provider_model_name,
            prompt_key=prompt_key,
            prompt_version=prompt_version.version,
            prompt_hash=prompt_version.prompt_hash,
            execution_id=execution_id,
            token_usage=TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0, estimated=True),
            estimated_cost=Decimal("0"),
            latency_ms=0,
            finish_reason=FinishReason.STOP,
            fallback_used=True,
            metadata={"fallback_reason": "retrieval_empty"},
        )

    def _find_usage_record(self, execution_id: str) -> AIUsageRecord | None:
        for record in self.ai_core.accounting_service.list_recent(limit=500):
            if record.execution_id == execution_id:
                return record
        return None


def _citation_payload(citation: RetrievalCitationData, quoted_text: str) -> dict:
    return {
        "chunk_id": citation.chunk_id,
        "document_id": citation.document_id,
        "document_version_id": citation.document_version_id,
        "citation_index": citation.citation_index,
        "similarity_score": Decimal(str(citation.score)),
        "source_title": citation.source_title,
        "source_type": citation.source_type,
        "page_number": citation.page_number,
        "section_title": citation.section_title,
        "quoted_text": quoted_text,
    }


def _prompt_version_to_int(version: str | None) -> int | None:
    if version is None:
        return None
    digits = "".join(character for character in version if character.isdigit())
    return int(digits) if digits else None

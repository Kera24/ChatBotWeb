from dataclasses import dataclass, field, replace
from decimal import Decimal
from time import perf_counter

from sqlalchemy.orm import Session

from app.ai.accounting import AIUsageRecord
from app.ai.contracts import FinishReason, TokenUsage
from app.ai.dependencies import AICoreContainer
from app.ai.errors import AIProviderError
from app.ai.guardrails.answer_constraints import AnswerConstraints, AnswerDecision, build_answer_constraints
from app.ai.guardrails.citation_policy import verify_citations
from app.ai.guardrails.document_sanitizer import sanitise_evidence_content
from app.ai.guardrails.evidence_confidence import ChunkEvidenceSignal, compute_evidence_confidence
from app.ai.guardrails.evidence_sufficiency import EvidenceSufficiencyV1Verifier, EvidenceVerifier
from app.ai.guardrails.input_policy import evaluate_input_policy
from app.ai.guardrails.output_safety import check_output_safety
from app.ai.guardrails.reason_codes import GuardrailReasonCode
from app.ai.model_registry import ModelConfig
from app.ai.service import AICoreGenerateInput
from app.core.config import settings
from app.db.models.prompt import LAYER_PLATFORM_CORE
from app.observability import context as trace_stages
from app.observability.ai_trace_recorder import AITraceRecorder, NoOpAITraceRecorder, RetrievalTraceEntry
from app.observability.context import AITraceContext, new_trace_id
from app.observability.otel_metrics import (
    record_evidence_confidence_outcome,
    record_evidence_verifier_outcome,
    record_query_transformation_outcome,
    record_reranker_outcome,
    record_retrieval_fusion,
)
from app.prompts.resolution import ResolvedComposite, resolve_composite_prompt
from app.repositories import conversation_repository
from app.access.widget_admin.service import WidgetAdminNotFound, get_current_draft, get_widget
from app.repositories.workspace_repository import get_workspace_for_organisation
from app.services.conversation import (
    append_assistant_message,
    append_user_message,
    attach_citations_to_assistant_message,
    start_conversation,
)
from app.services.embeddings import EmbeddingProvider
from app.services.query_transformation import IdentityQueryTransformer, QueryTransformer, transform_query
from app.services.reranking import NoOpReranker, Reranker
from app.services.retrieval_context import (
    RetrievalCitationData,
    RetrievalContextBlockData,
    RetrievalDebugInfo,
    assemble_retrieval_context,
)
from app.services.retrieval_v3 import assemble_v3_retrieval_context


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _retrieval_debug_metadata(debug: RetrievalDebugInfo | None) -> dict:
    """Retrieval V2 Phase 1 (docs/future/HybridRetrieval.md) - non-guardrail
    provenance stashed in RAGOrchestrationResult.metadata (an existing
    free-form field) so app.evaluation.engine._score_result can surface it in
    EvaluationResult.retrieval_metrics_json for the bake-off, without a new
    column/migration. Empty dict when retrieval never ran (e.g. an
    input-policy block before retrieval)."""
    if debug is None:
        return {}
    return {
        "retrieval_strategy": debug.strategy,
        "dense_candidate_count": debug.dense_candidate_count,
        "lexical_candidate_count": debug.lexical_candidate_count,
        "fused_candidate_count": debug.fused_candidate_count,
        "dense_latency_ms": debug.dense_latency_ms,
        "lexical_latency_ms": debug.lexical_latency_ms,
        "fusion_latency_ms": debug.fusion_latency_ms,
        "reranker_enabled": debug.reranker_enabled,
        "reranker_provider": debug.reranker_provider,
        "reranker_model": debug.reranker_model,
        "reranker_candidate_count": debug.reranker_candidate_count,
        "reranker_selected_count": debug.reranker_selected_count,
        "reranker_latency_ms": debug.reranker_latency_ms,
        "reranker_status": debug.reranker_status,
        "query_transformer_enabled": debug.query_transformer_enabled,
        "query_transformer_type": debug.query_transformer_type,
        "query_transformer_provider": debug.query_transformer_provider,
        "query_transformer_model": debug.query_transformer_model,
        "query_transformer_status": debug.query_transformer_status,
        "query_transformer_latency_ms": debug.query_transformer_latency_ms,
        "query_transformer_query_count": debug.query_transformer_query_count,
        "query_transformer_raw_candidate_count": debug.query_transformer_raw_candidate_count,
        "query_transformer_deduplicated_candidate_count": debug.query_transformer_deduplicated_candidate_count,
    }


DEFAULT_RAG_PROMPT_KEY = "grounded_rag_answer"
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
    assistant_id: str | None = None
    channel: str = "dashboard_test"
    conversation_id: str | None = None
    model_key: str | None = None
    prompt_key: str | None = None
    retrieval_limit: int | None = None
    max_context_chars: int | None = None
    min_similarity_score: float | None = None
    metadata: dict | None = None
    simulate_failure: bool = False
    simulate_timeout: bool = False
    trace_context: AITraceContext | None = None
    # Forces prompt resolution to use one specific PromptVersion for its layer
    # (see app.prompts.resolution) instead of the widget's current
    # deployment/experiment assignment. Set only by
    # app.evaluation.prompt_promotion_gate / app.evaluation.engine when
    # gating a candidate version - never set for organic production traffic.
    prompt_version_override_id: str | None = None
    # Retrieval V2 Phase 1 (docs/future/HybridRetrieval.md) - overrides
    # settings.RETRIEVAL_STRATEGY for this one request. None (the default)
    # means "use whatever the deployment is globally configured for" - set
    # explicitly by app.evaluation.engine for a bake-off run, and available
    # for a future per-workspace flag; never set for organic production
    # traffic today.
    retrieval_strategy: str | None = None
    # Retrieval V2 Phase 2 (docs/future/Reranking.md) - overrides
    # settings.RERANKER_DENSE_CANDIDATE_POOL_SIZE/RERANKER_FINAL_TOP_K for
    # this one request. None (the default) means "use the deployment's
    # global configuration" - set explicitly by app.evaluation.engine for a
    # controlled candidate-pool/top-k experiment (Part 9); never set for
    # organic production traffic today.
    reranker_candidate_pool_size: int | None = None
    reranker_final_top_k: int | None = None


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
    trace_id: str | None = None


@dataclass(frozen=True)
class RAGOrchestratorDependencies:
    db: Session
    ai_core: AICoreContainer
    embedding_provider: EmbeddingProvider
    trace_recorder: AITraceRecorder | None = None
    # Retrieval V2 Phase 2 (docs/future/Reranking.md). Defaults to
    # NoOpReranker (reranking disabled) in RAGOrchestrator.__init__ for every
    # existing call site that doesn't construct one explicitly - same
    # pattern as trace_recorder above.
    reranker: Reranker | None = None
    # Production traffic (default False) falls back safely to unmodified
    # dense ordering on any reranker failure; evaluation runs
    # (app.evaluation.engine) set this True so a reranker defect surfaces as
    # a hard case failure instead of silently "succeeding" via that same
    # fallback - see app.services.reranking.rerank_candidates.
    reranker_fail_loud: bool = False
    # Retrieval V2 Phase 3 (docs/future/QueryRewrite.md). Defaults to
    # IdentityQueryTransformer (transformation disabled, one retrieval query -
    # the original question, unchanged) for every existing call site that
    # doesn't construct one explicitly - same pattern as reranker above.
    query_transformer: QueryTransformer | None = None
    # Production traffic (default False) falls back safely to the identity
    # plan (original query only) on any transformer failure; evaluation runs
    # set this True so a transformer defect surfaces as a hard case failure
    # instead of silently "succeeding" via that same fallback - see
    # app.services.query_transformation.transform_query.
    query_transformer_fail_loud: bool = False
    # Evidence Sufficiency V2 (docs/future/GuardrailsV2.md task). Defaults to
    # EvidenceSufficiencyV1Verifier (today's exact production behaviour) for
    # every existing call site that doesn't construct one explicitly - same
    # pattern as reranker/query_transformer above. See
    # app.ai.guardrails.evidence_sufficiency's V2 section docstring for what
    # V2 changes and why; settings.EVIDENCE_VERIFIER_VERSION controls which
    # one organic production traffic actually gets.
    evidence_verifier: EvidenceVerifier | None = None
    # Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md).
    # Defaults to False (today's exact production behaviour: dense_only/
    # hybrid_rrf via assemble_retrieval_context, no evidence-confidence/
    # constraints stage) for every existing call site - same one-flag,
    # default-off pattern as every other experimental dependency above. When
    # True: retrieval goes through app.services.retrieval_v3's hybrid
    # dense+lexical+RRF+reranker composition (full per-chunk provenance
    # preserved), and an additive Evidence Confidence / AnswerConstraints
    # stage runs after evidence sufficiency - never replaces or reorders any
    # existing stage, only adds to what already runs.
    use_v3_retrieval: bool = False


class RAGOrchestrator:
    def __init__(self, dependencies: RAGOrchestratorDependencies) -> None:
        self.db = dependencies.db
        self.ai_core = dependencies.ai_core
        self.embedding_provider = dependencies.embedding_provider
        # Every existing call site that doesn't construct a trace_recorder
        # keeps working unchanged - see app.observability.ai_trace_recorder.
        self.trace_recorder = dependencies.trace_recorder or NoOpAITraceRecorder()
        # Every existing call site that doesn't construct a reranker keeps
        # working unchanged - see app.services.reranking.
        self.reranker = dependencies.reranker or NoOpReranker()
        self.reranker_fail_loud = dependencies.reranker_fail_loud
        # Every existing call site that doesn't construct a query_transformer
        # keeps working unchanged - see app.services.query_transformation.
        self.query_transformer = dependencies.query_transformer or IdentityQueryTransformer()
        self.query_transformer_fail_loud = dependencies.query_transformer_fail_loud
        # Every existing call site that doesn't construct an evidence_verifier
        # keeps working unchanged - see app.ai.guardrails.evidence_sufficiency.
        self.evidence_verifier = dependencies.evidence_verifier or EvidenceSufficiencyV1Verifier()
        self.use_v3_retrieval = dependencies.use_v3_retrieval

    def answer(self, request: RAGOrchestrationRequest) -> RAGOrchestrationResult:
        trace_context = request.trace_context or AITraceContext(trace_id=new_trace_id())
        request_started_at = perf_counter()
        self.trace_recorder.start_trace(
            trace_context,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            assistant_id=request.assistant_id,
            channel=request.channel,
        )
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_REQUEST_ACCEPTED, status="ok")

        tenant_stage_started_at = perf_counter()
        try:
            self._validate_workspace(request)
            assistant = self._resolve_assistant(request)
            assistant_id = assistant.id if assistant is not None else None
            conversation = self._resolve_conversation(request, assistant_id=assistant_id)
        except RAGOrchestratorError as exc:
            self.trace_recorder.record_stage(
                trace_context, trace_stages.STAGE_AUTH_TENANT_RESOLUTION, status="error",
                latency_ms=_elapsed_ms(tenant_stage_started_at), error_class=exc.code,
            )
            self.trace_recorder.finish_trace(
                trace_context, status="failed", answer_state=None, fallback_used=False,
                total_latency_ms=_elapsed_ms(request_started_at), error_class=exc.code,
            )
            raise
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_AUTH_TENANT_RESOLUTION, status="ok",
            latency_ms=_elapsed_ms(tenant_stage_started_at),
        )
        trace_context = replace(trace_context, conversation_id=conversation.id)

        user_message = append_user_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            content=request.query,
            metadata_json=request.metadata,
        )

        # Resolved from settings.DEFAULT_AI_MODEL_KEY (env-driven, see
        # app.ai.dependencies.create_ai_core) rather than a hardcoded mock
        # literal, so a request that doesn't pin a specific model_key follows
        # whichever provider AI_PROVIDER actually configured - the mechanism
        # that makes "no silent mock fallback in production" hold for both
        # the dashboard test endpoint and the public widget adapter, which
        # both normally call answer() with model_key=None.
        model_key = request.model_key or settings.DEFAULT_AI_MODEL_KEY
        prompt_key = request.prompt_key or DEFAULT_RAG_PROMPT_KEY
        model = self.ai_core.model_registry.get(model_key, require_enabled=True)

        # Layers C+D: capability/intent boundaries and direct prompt-injection
        # defence run BEFORE retrieval or generation - a blocked request never
        # reaches the AI provider at all, so this is fully enforced and
        # testable regardless of which provider is configured.
        input_policy_started_at = perf_counter()
        input_verdict = evaluate_input_policy(request.query)
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_INPUT_POLICY,
            status="ok" if input_verdict.allowed else "blocked",
            latency_ms=_elapsed_ms(input_policy_started_at),
            reason_code=None if input_verdict.allowed else input_verdict.reason_code.value,
        )
        self.trace_recorder.record_guardrail(
            trace_context, layer="C+D", guardrail_name="input_policy",
            verdict="passed" if input_verdict.allowed else "blocked", blocked=not input_verdict.allowed,
            reason_code=None if input_verdict.allowed else input_verdict.reason_code.value,
        )
        if not input_verdict.allowed:
            return self._persist_fallback(
                request=request, conversation_id=conversation.id, user_message_id=user_message.id,
                model=model, prompt_key=prompt_key, trace_context=trace_context, request_started_at=request_started_at,
                content=input_verdict.safe_message or FALLBACK_ANSWER, reason_code=input_verdict.reason_code.value,
            )

        retrieval_limit = request.retrieval_limit or settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
        max_context_chars = request.max_context_chars or settings.RETRIEVAL_MAX_CONTEXT_CHARS
        allowed_document_ids = self._knowledge_scope_for_request(request, assistant)

        # Retrieval V2 Phase 3 (docs/future/QueryRewrite.md) - produces
        # ADDITIONAL retrieval-only query strings alongside request.query.
        # HARD REQUIREMENT: query_plan.retrieval_queries is only ever passed
        # into assemble_retrieval_context below - request.query (the original
        # question) remains untouched everywhere else in this method
        # (evidence sufficiency, prompt resolution, generation variables,
        # persisted user_message content) - see this module's and
        # app.services.query_transformation's docstrings.
        query_plan = transform_query(self.query_transformer, query=request.query, fail_loud=self.query_transformer_fail_loud)

        effective_min_similarity_score = request.min_similarity_score if request.min_similarity_score is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        retrieval_started_at = perf_counter()
        if self.use_v3_retrieval:
            # Retrieval & Answer Pipeline V3 experiment - hybrid dense+lexical
            # candidate generation with full provenance preserved (see
            # app.services.retrieval_v3's own docstring for why this is a
            # separate composition rather than a change to
            # assemble_retrieval_context, which stays the untouched baseline
            # path below). Reuses the SAME bounded pool-size settings
            # hybrid_rrf already uses - no new candidate-pool config surface.
            v3_result = assemble_v3_retrieval_context(
                self.db,
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                query=request.query,
                provider=self.embedding_provider,
                document_ids=allowed_document_ids,
                dense_pool_size=settings.RETRIEVAL_DENSE_CANDIDATE_POOL_SIZE,
                lexical_pool_size=settings.RETRIEVAL_LEXICAL_CANDIDATE_POOL_SIZE,
                rrf_k=settings.RETRIEVAL_RRF_K,
                fused_pool_size=settings.RETRIEVAL_HYBRID_FINAL_TOP_K,
                reranker=self.reranker,
                reranker_top_k=request.reranker_final_top_k or settings.RERANKER_FINAL_TOP_K,
                reranker_fail_loud=self.reranker_fail_loud,
                max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
                max_context_chars=max_context_chars,
            )
            retrieval = replace(
                v3_result.context,
                retrieval_debug=RetrievalDebugInfo(
                    strategy="hybrid_rrf_v3",
                    dense_candidate_count=v3_result.debug.dense_candidate_count,
                    lexical_candidate_count=v3_result.debug.lexical_candidate_count,
                    fused_candidate_count=v3_result.debug.fused_candidate_count,
                    dense_latency_ms=0, lexical_latency_ms=0, fusion_latency_ms=0,
                    reranker_enabled=v3_result.debug.reranker_enabled,
                    reranker_provider=v3_result.debug.reranker_provider,
                    reranker_model=v3_result.debug.reranker_model,
                    reranker_candidate_count=v3_result.debug.fused_candidate_count if v3_result.debug.reranker_enabled else 0,
                    reranker_selected_count=len(v3_result.context.context_blocks) if v3_result.debug.reranker_enabled else 0,
                    reranker_status=v3_result.debug.reranker_status,
                ),
            )
        else:
            retrieval = assemble_retrieval_context(
                self.db,
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                query=request.query,
                search_limit=retrieval_limit,
                max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
                max_context_chars=max_context_chars,
                provider=self.embedding_provider,
                document_ids=allowed_document_ids,
                min_similarity_score=effective_min_similarity_score,
                retrieval_strategy=request.retrieval_strategy,
                reranker=self.reranker,
                reranker_candidate_pool_size=request.reranker_candidate_pool_size,
                reranker_final_top_k=request.reranker_final_top_k,
                reranker_fail_loud=self.reranker_fail_loud,
                query_plan=query_plan,
            )
        retrieval_latency_ms = _elapsed_ms(retrieval_started_at)
        # Embedding happens inside assemble_retrieval_context and isn't
        # separately timed there - recorded as its own (unmeasured, bundled
        # into retrieval_latency_ms) stage so the pipeline stays explainable
        # even without deeper instrumentation of app.services.vector_search.
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_QUERY_EMBEDDING, status="ok")
        debug = retrieval.retrieval_debug
        retrieval_safe_counts = {"chunks_returned": len(retrieval.context_blocks), "total_context_chars": retrieval.total_context_chars}
        if debug is not None:
            retrieval_safe_counts.update(
                {
                    "retrieval_strategy": debug.strategy,
                    "dense_candidate_count": debug.dense_candidate_count,
                    "lexical_candidate_count": debug.lexical_candidate_count,
                    "fused_candidate_count": debug.fused_candidate_count,
                }
            )
            record_retrieval_fusion(
                strategy=debug.strategy,
                dense_candidate_count=debug.dense_candidate_count,
                lexical_candidate_count=debug.lexical_candidate_count,
                fused_candidate_count=debug.fused_candidate_count,
                selected_top_k=len(retrieval.context_blocks),
            )
            record_reranker_outcome(
                enabled=debug.reranker_enabled,
                provider=debug.reranker_provider,
                model=debug.reranker_model,
                candidate_count=debug.reranker_candidate_count,
                selected_count=debug.reranker_selected_count,
                latency_ms=debug.reranker_latency_ms,
                status=debug.reranker_status,
            )
            record_query_transformation_outcome(
                enabled=debug.query_transformer_enabled,
                strategy=debug.query_transformer_type,
                provider=debug.query_transformer_provider,
                model=debug.query_transformer_model,
                status=debug.query_transformer_status,
                latency_ms=debug.query_transformer_latency_ms,
                generated_query_count=debug.query_transformer_query_count,
                raw_candidate_count=debug.query_transformer_raw_candidate_count,
                deduplicated_candidate_count=debug.query_transformer_deduplicated_candidate_count,
            )
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_RETRIEVAL, status="ok" if retrieval.context_blocks else "empty",
            latency_ms=retrieval_latency_ms,
            safe_counts=retrieval_safe_counts,
        )
        # Only chunks actually selected into the context window are visible
        # here - app.services.retrieval_context does not currently return
        # candidates rejected before selection, so "rejected chunk" capture
        # is not yet implemented (see docs/.../AI_Trace_Data_and_Privacy_Policy.md
        # deferred-scope notes).
        self.trace_recorder.record_retrieval(
            trace_context,
            entries=[
                RetrievalTraceEntry(
                    rank=index + 1, selected=True, chunk_id=block.chunk_id, document_id=block.document_id,
                    similarity_score=block.score, source_title=block.source_title, content=block.content,
                )
                for index, block in enumerate(retrieval.context_blocks)
            ],
        )

        if not retrieval.context_blocks:
            return self._persist_fallback(
                request=request, conversation_id=conversation.id, user_message_id=user_message.id,
                model=model, prompt_key=prompt_key, trace_context=trace_context, request_started_at=request_started_at,
                retrieval_debug=retrieval.retrieval_debug,
            )

        # Layer F: citation enforcement (defence-in-depth assertion - see
        # app.ai.guardrails.citation_policy's docstring for why this should
        # never actually fire given the retrieval query's own scoping).
        citation_verdict = verify_citations(retrieval.citations, allowed_document_ids=allowed_document_ids)
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_CITATION_VALIDATION,
            status="ok" if citation_verdict.passed else "blocked",
            reason_code=None if citation_verdict.passed else citation_verdict.reason_code.value,
        )
        self.trace_recorder.record_guardrail(
            trace_context, layer="F", guardrail_name="citation_policy",
            verdict="passed" if citation_verdict.passed else "blocked", blocked=not citation_verdict.passed,
            reason_code=None if citation_verdict.passed else citation_verdict.reason_code.value,
        )
        if not citation_verdict.passed:
            return self._persist_fallback(
                request=request, conversation_id=conversation.id, user_message_id=user_message.id,
                model=model, prompt_key=prompt_key, trace_context=trace_context, request_started_at=request_started_at,
                content=citation_verdict.safe_message or FALLBACK_ANSWER, reason_code=citation_verdict.reason_code.value,
                retrieval_debug=retrieval.retrieval_debug,
            )

        # Layer E: strip injected-instruction-style text from retrieved
        # document content before it is ever assembled into context - the
        # generation model never sees the attempted override.
        sanitised_blocks = [_sanitise_block(block) for block in retrieval.context_blocks]
        context = "\n\n".join(block.context_text for block in sanitised_blocks)
        modified_count = sum(1 for original, sanitised in zip(retrieval.context_blocks, sanitised_blocks, strict=True) if original.content != sanitised.content)
        self.trace_recorder.record_guardrail(
            trace_context, layer="E", guardrail_name="document_sanitizer", verdict="modified" if modified_count else "passed",
            blocked=False, safe_detail={"chunks_sanitised": modified_count},
        )

        # Layers A+B: does the retrieved evidence actually support the
        # *specific* fact requested, not just the general topic (see
        # app.ai.guardrails.evidence_sufficiency for the full multi-signal
        # method - requested-attribute/value-type extraction, sentence-level
        # proximity, and retrieval-confidence-based domain relevance - and
        # its honest limitations).
        evidence_started_at = perf_counter()
        evidence_verdict = self.evidence_verifier.verify(
            question=request.query,
            chunk_contents=[block.content for block in sanitised_blocks],
            chunk_titles=[block.source_title for block in sanitised_blocks],
            retrieval_scores=[block.score for block in sanitised_blocks],
        )
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_EVIDENCE_SUFFICIENCY,
            status="ok" if evidence_verdict.sufficient else "blocked",
            latency_ms=_elapsed_ms(evidence_started_at),
            reason_code=None if evidence_verdict.sufficient else evidence_verdict.reason_code.value,
        )
        self.trace_recorder.record_guardrail(
            trace_context, layer="A+B", guardrail_name="evidence_sufficiency",
            verdict="passed" if evidence_verdict.sufficient else "blocked", blocked=not evidence_verdict.sufficient,
            reason_code=None if evidence_verdict.sufficient else evidence_verdict.reason_code.value,
            safe_detail={"evidence_verifier_version": self.evidence_verifier.version},
        )
        record_evidence_verifier_outcome(
            version=self.evidence_verifier.version,
            verdict="sufficient" if evidence_verdict.sufficient else "insufficient",
            reason_code=evidence_verdict.reason_code.value,
            chunks_considered=len(sanitised_blocks),
            conflict_detected=evidence_verdict.reason_code == GuardrailReasonCode.CONFLICTING_EVIDENCE,
            latency_ms=_elapsed_ms(evidence_started_at),
        )
        # Grounding is currently only functionally covered by evidence
        # sufficiency above - app.ai.guardrails.grounding.verify_grounding is
        # not wired into the live pipeline, so this stage is recorded as
        # explicitly skipped rather than fabricating a pass/fail it never ran.
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_GROUNDING_VERIFICATION, status="skipped", reason_code="not_wired_into_pipeline")

        # Retrieval & Answer Pipeline V3 experiment - Evidence Confidence
        # (app.ai.guardrails.evidence_confidence) + AnswerConstraints
        # (app.ai.guardrails.answer_constraints) additive stage. Purely
        # derived from evidence_verdict/retrieval provenance already
        # computed above - no model call, no new network I/O, no change to
        # the guardrail chain's pass/fail determination itself (constraints
        # never grant an answer evidence_sufficiency rejected). Only changes
        # observable behaviour in two additive ways when use_v3_retrieval is
        # on: (1) a CONFLICTING_EVIDENCE verdict that looks like a genuine
        # scope choice ("which plan do you mean?") gets a more specific
        # fallback message/reason_code than the generic conflicting-evidence
        # one; (2) generation context is restricted to only
        # direct_support-outcome chunks (Part 11's "the model must never see
        # rejected evidence as authoritative context where avoidable").
        fallback_content = evidence_verdict.safe_message or FALLBACK_ANSWER
        fallback_reason_code = evidence_verdict.reason_code.value
        if self.use_v3_retrieval:
            chunk_signals = tuple(
                ChunkEvidenceSignal(
                    chunk_id=block.chunk_id, outcome=outcome,
                    dense_score=block.dense_score, lexical_score=block.lexical_score, rerank_score=block.rerank_score,
                    source_channels=block.source_channels,
                    matched_value=detail.matched_value if detail else None,
                    matched_sentence=detail.matched_sentence if detail else None,
                )
                for block, outcome, detail in zip(
                    sanitised_blocks, evidence_verdict.chunk_outcomes,
                    evidence_verdict.chunk_support_details or (None,) * len(evidence_verdict.chunk_outcomes),
                    strict=True,
                )
            ) if len(evidence_verdict.chunk_outcomes) == len(sanitised_blocks) else ()
            v3_confidence = compute_evidence_confidence(verdict=evidence_verdict, chunk_signals=chunk_signals)
            v3_constraints = build_answer_constraints(verdict=evidence_verdict, confidence=v3_confidence, chunk_signals=chunk_signals)
            self.trace_recorder.record_guardrail(
                trace_context, layer="V3", guardrail_name="evidence_confidence",
                verdict=v3_constraints.decision.value, blocked=not v3_constraints.answer_allowed,
                reason_code=v3_constraints.reason_codes[-1] if v3_constraints.reason_codes else None,
                safe_detail={"confidence_score": v3_confidence.score, "confidence_band": v3_confidence.band.value},
            )
            record_evidence_confidence_outcome(
                decision=v3_constraints.decision.value, confidence_band=v3_confidence.band.value,
                conflicting_evidence=v3_constraints.conflicting_evidence, clarification_required=v3_constraints.clarification_required,
            )
            if v3_constraints.decision == AnswerDecision.CLARIFICATION_REQUIRED:
                fallback_content = v3_constraints.safe_message or fallback_content
                fallback_reason_code = v3_constraints.reason_codes[-1] if v3_constraints.reason_codes else fallback_reason_code
            elif v3_constraints.answer_allowed and v3_constraints.allowed_chunk_ids:
                allowed_ids = set(v3_constraints.allowed_chunk_ids)
                filtered_pairs = [
                    (citation, block) for citation, block in zip(retrieval.citations, sanitised_blocks, strict=True)
                    if block.chunk_id in allowed_ids
                ]
                if filtered_pairs:  # fail-safe: never filter down to zero chunks - fall through with the full set instead
                    filtered_citations, sanitised_blocks = (list(x) for x in zip(*filtered_pairs))
                    context = "\n\n".join(block.context_text for block in sanitised_blocks)
                    retrieval = replace(retrieval, citations=filtered_citations)

        if not evidence_verdict.sufficient:
            return self._persist_fallback(
                request=request, conversation_id=conversation.id, user_message_id=user_message.id,
                model=model, prompt_key=prompt_key, trace_context=trace_context, request_started_at=request_started_at,
                content=fallback_content, reason_code=fallback_reason_code,
                retrieval_debug=retrieval.retrieval_debug,
            )

        # Composite prompt resolution (app.prompts.resolution) is fully
        # additive/opt-in: a widget with zero prompt-management activity gets
        # `composite is None` back and generation below proceeds exactly as
        # before. Fail-open (log a degraded stage, fall through to the
        # default) for organic traffic; fail-loud (propagate) only when the
        # evaluation/promotion-gate engine explicitly asked for one specific
        # candidate version - see docs/architecture/prompts.md.
        composite: ResolvedComposite | None = None
        composite_degraded = False
        try:
            composite = resolve_composite_prompt(
                self.db, prompt_key=prompt_key, organisation_id=request.organisation_id, workspace_id=request.workspace_id,
                widget_id=assistant_id, question=request.query, context=context, conversation_id=conversation.id,
                prompt_version_override_id=request.prompt_version_override_id,
            )
        except Exception:
            if request.prompt_version_override_id is not None:
                raise
            composite = None
            composite_degraded = True
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_PROMPT_CONSTRUCTION,
            status="degraded" if composite_degraded else "ok",
            reason_code="prompt_resolution_fallback" if composite_degraded else None,
            provider_model_config_version=composite.rendered.version if composite is not None else prompt_key,
        )
        resolved_layer_version_ids = composite.resolved_layer_version_ids if composite is not None else None
        experiment_id = composite.experiment_id if composite is not None else None
        experiment_arm = composite.experiment_arm if composite is not None else None
        composite_prompt_version_id = resolved_layer_version_ids.get(LAYER_PLATFORM_CORE) if resolved_layer_version_ids else None

        execution_id = self.ai_core.accounting_service.create_execution_id()
        provider_started_at = perf_counter()
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
                    override_rendered_prompt=composite.rendered if composite is not None else None,
                )
            )
        except AIProviderError as exc:
            record = self._find_usage_record(execution_id)
            self.trace_recorder.record_stage(
                trace_context, trace_stages.STAGE_PROVIDER_GENERATION, status="error",
                latency_ms=_elapsed_ms(provider_started_at), error_class=exc.code,
            )
            self.trace_recorder.record_model_call(
                trace_context, model=model, provider_model_name=model.provider_model_name, prompt_key=prompt_key,
                prompt_version=record.prompt_version if record else None, prompt_hash=record.prompt_hash if record else None,
                token_usage=TokenUsage(
                    input_tokens=record.prompt_tokens if record else 0,
                    output_tokens=record.completion_tokens if record else 0,
                    total_tokens=record.total_tokens if record else 0,
                ),
                latency_ms=record.latency_ms if record else _elapsed_ms(provider_started_at),
                finish_reason=(record.finish_reason.value if record else FinishReason.ERROR.value),
                outcome="failed", error_code=exc.code,
                prompt_version_id=composite_prompt_version_id, experiment_id=experiment_id, experiment_arm=experiment_arm,
                resolved_layer_version_ids=resolved_layer_version_ids,
            )
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
            self.trace_recorder.finish_trace(
                trace_context, status="failed", answer_state="failed", fallback_used=False,
                total_latency_ms=_elapsed_ms(request_started_at), provider_key=model.provider_key, model_key=model.model_key,
                provider_model_name=model.provider_model_name, error_class=exc.code,
            )
            raise RAGProviderExecutionError(
                "AI provider execution failed while preserving conversation state.",
                provider_error_code=exc.code,
                execution_id=execution_id,
                assistant_message_id=assistant_message.id,
            ) from exc

        record = self._find_usage_record(execution_id)
        estimated_cost = record.total_estimated_cost if record else Decimal("0")
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_PROVIDER_GENERATION, status="ok", latency_ms=ai_response.latency_ms)
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_STRUCTURED_OUTPUT_PARSING, status="ok")
        self.trace_recorder.record_model_call(
            trace_context, model=model, provider_model_name=ai_response.provider_model_name, prompt_key=ai_response.prompt_key,
            prompt_version=ai_response.prompt_version, prompt_hash=ai_response.prompt_hash, token_usage=ai_response.token_usage,
            latency_ms=ai_response.latency_ms, finish_reason=ai_response.finish_reason.value, outcome="success",
            raw_prompt=context, raw_response=ai_response.text,
            prompt_version_id=composite_prompt_version_id, experiment_id=experiment_id, experiment_arm=experiment_arm,
            resolved_layer_version_ids=resolved_layer_version_ids,
        )

        # Layers G+H: never persist or return raw generated text without a
        # post-generation check - markup is always neutralised, and any
        # secret/prompt-leakage pattern is replaced with a safe refusal
        # rather than partially redacted (see output_safety's docstring).
        output_safety_started_at = perf_counter()
        output_verdict = check_output_safety(ai_response.text)
        final_answer_state = "answered" if output_verdict.safe else "fallback"
        self.trace_recorder.record_stage(
            trace_context, trace_stages.STAGE_OUTPUT_SANITISATION, status="ok" if output_verdict.safe else "blocked",
            latency_ms=_elapsed_ms(output_safety_started_at),
            reason_code=None if output_verdict.safe else output_verdict.reason_code.value,
        )
        self.trace_recorder.record_guardrail(
            trace_context, layer="G+H", guardrail_name="output_safety",
            verdict="passed" if output_verdict.safe else "blocked", blocked=not output_verdict.safe,
            reason_code=None if output_verdict.safe else output_verdict.reason_code.value,
        )
        assistant_message = append_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            content=output_verdict.sanitised_text,
            answer_state=final_answer_state,
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
                "guardrail_reason_code": output_verdict.reason_code.value,
                "prompt_version": ai_response.prompt_version,
                "provider_metadata": ai_response.provider_metadata.model_dump(mode="json"),
                "ai_response_metadata": ai_response.metadata,
                "retrieval": {
                    "requested_limit": retrieval_limit,
                    "returned_chunks": len(retrieval.context_blocks),
                    "total_context_chars": retrieval.total_context_chars,
                },
                # Composite prompt identity (see app.prompts.resolution) is
                # kept here as supplementary metadata rather than a new
                # ChatMessage column - ChatMessage.prompt_version (Integer)
                # cannot represent a composite label, and the authoritative
                # structured record already lives on AIModelCallTrace.
                "resolved_layer_version_ids": resolved_layer_version_ids,
                "experiment_id": experiment_id,
                "experiment_arm": experiment_arm,
            },
        )
        if output_verdict.safe:
            citation_payloads = [_citation_payload(citation, block.content) for citation, block in zip(retrieval.citations, sanitised_blocks, strict=True)]
        else:
            citation_payloads = []
        persisted_citations = attach_citations_to_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            citations=citation_payloads,
        )
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_PERSISTENCE, status="ok", safe_counts={"citations_persisted": len(persisted_citations)})
        total_latency_ms = _elapsed_ms(request_started_at)
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_RESPONSE_COMPLETED, status="ok", latency_ms=total_latency_ms)
        self.trace_recorder.finish_trace(
            trace_context, status="completed", answer_state=final_answer_state, fallback_used=not output_verdict.safe,
            total_latency_ms=total_latency_ms, provider_key=ai_response.provider_key, model_key=ai_response.model_key,
            provider_model_name=ai_response.provider_model_name, embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name, total_tokens=ai_response.token_usage.total_tokens,
            estimated_cost=estimated_cost,
        )
        return RAGOrchestrationResult(
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=output_verdict.sanitised_text,
            answer_state=final_answer_state,
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
            fallback_used=not output_verdict.safe,
            metadata={
                "total_context_chars": retrieval.total_context_chars,
                "guardrail_reason_code": output_verdict.reason_code.value,
                **_retrieval_debug_metadata(retrieval.retrieval_debug),
            },
            trace_id=trace_context.trace_id,
        )

    def _validate_workspace(self, request: RAGOrchestrationRequest) -> None:
        workspace = get_workspace_for_organisation(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
        )
        if workspace is None:
            raise RAGTenantContextError("Workspace not found for organisation.")

    def _resolve_assistant(self, request: RAGOrchestrationRequest):
        if request.assistant_id is None:
            return None
        try:
            return get_widget(self.db, organisation_id=request.organisation_id, workspace_id=request.workspace_id, widget_id=request.assistant_id)
        except WidgetAdminNotFound as exc:
            raise RAGTenantContextError("Assistant not found for workspace.") from exc

    def _knowledge_scope_for_request(self, request: RAGOrchestrationRequest, assistant) -> list[str] | None:
        if assistant is None:
            return (request.metadata or {}).get("knowledge_document_ids") or None
        try:
            draft = get_current_draft(self.db, widget=assistant)
        except WidgetAdminNotFound:
            return []
        return list(draft.knowledge_scope_json or [])

    def _resolve_conversation(self, request: RAGOrchestrationRequest, *, assistant_id: str | None):
        if request.conversation_id is None:
            return start_conversation(
                self.db,
                organisation_id=request.organisation_id,
                workspace_id=request.workspace_id,
                channel=request.channel,
                metadata_json={**(request.metadata or {}), **({"assistant_id": assistant_id, "widget_id": assistant_id} if assistant_id else {})},
                widget_id=assistant_id,
            )
        conversation = conversation_repository.get_conversation(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=request.conversation_id,
            widget_id=assistant_id,
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
        trace_context: AITraceContext,
        request_started_at: float,
        content: str = FALLBACK_ANSWER,
        reason_code: str = GuardrailReasonCode.RETRIEVAL_EMPTY.value,
        answer_state: str = "fallback",
        retrieval_debug: RetrievalDebugInfo | None = None,
    ) -> RAGOrchestrationResult:
        prompt_version = self.ai_core.prompt_registry.resolve_active(prompt_key)
        execution_id = self.ai_core.accounting_service.create_execution_id()
        assistant_message = append_assistant_message(
            self.db,
            organisation_id=request.organisation_id,
            workspace_id=request.workspace_id,
            conversation_id=conversation_id,
            content=content,
            answer_state=answer_state,
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
            # `guardrail_reason_code` is metadata only, never a new answer_state
            # value - see app.ai.guardrails.reason_codes for why this keeps API
            # schema and dashboard rendering compatibility intact.
            metadata_json={"guardrail_reason_code": reason_code, "prompt_version": prompt_version.version},
        )
        total_latency_ms = _elapsed_ms(request_started_at)
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_PERSISTENCE, status="ok", safe_counts={"citations_persisted": 0})
        self.trace_recorder.record_stage(trace_context, trace_stages.STAGE_RESPONSE_COMPLETED, status="ok", latency_ms=total_latency_ms)
        self.trace_recorder.finish_trace(
            trace_context, status="completed", answer_state=answer_state, fallback_used=True,
            total_latency_ms=total_latency_ms, provider_key=model.provider_key, model_key=model.model_key,
            provider_model_name=model.provider_model_name, embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name, total_tokens=0, estimated_cost=Decimal("0"),
            metadata={"guardrail_reason_code": reason_code},
        )
        return RAGOrchestrationResult(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            answer=content,
            answer_state=answer_state,
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
            metadata={"guardrail_reason_code": reason_code, **_retrieval_debug_metadata(retrieval_debug)},
            trace_id=trace_context.trace_id,
        )

    def _find_usage_record(self, execution_id: str) -> AIUsageRecord | None:
        for record in self.ai_core.accounting_service.list_recent(limit=500):
            if record.execution_id == execution_id:
                return record
        return None


def _sanitise_block(block: RetrievalContextBlockData) -> RetrievalContextBlockData:
    """Layer E: applies document_sanitizer's injected-instruction stripping
    to one retrieved chunk, preserving the citation prefix (`[n] Title | ...`)
    unchanged - only the underlying document content is ever modified."""
    sanitised = sanitise_evidence_content(block.content)
    if not sanitised.was_modified:
        return block
    prefix = block.context_text[: len(block.context_text) - len(block.content)]
    return replace(block, content=sanitised.content, context_text=prefix + sanitised.content)


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

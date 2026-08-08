from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

# 14 pipeline stages an AI request passes through, in order. Mirrors the
# comment block at the top of RAGOrchestrator.answer() ("Layers A-H") plus the
# request-lifecycle boundaries that sit outside the orchestrator itself.
STAGE_REQUEST_ACCEPTED = "request_accepted"
STAGE_AUTH_TENANT_RESOLUTION = "auth_tenant_resolution"
STAGE_INPUT_POLICY = "input_policy"
STAGE_QUERY_EMBEDDING = "query_embedding"
STAGE_RETRIEVAL = "retrieval"
STAGE_EVIDENCE_SUFFICIENCY = "evidence_sufficiency"
STAGE_PROMPT_CONSTRUCTION = "prompt_construction"
STAGE_PROVIDER_GENERATION = "provider_generation"
STAGE_STRUCTURED_OUTPUT_PARSING = "structured_output_parsing"
STAGE_GROUNDING_VERIFICATION = "grounding_verification"
STAGE_CITATION_VALIDATION = "citation_validation"
STAGE_OUTPUT_SANITISATION = "output_sanitisation"
STAGE_PERSISTENCE = "persistence"
STAGE_RESPONSE_COMPLETED = "response_completed"

ALL_STAGES: tuple[str, ...] = (
    STAGE_REQUEST_ACCEPTED,
    STAGE_AUTH_TENANT_RESOLUTION,
    STAGE_INPUT_POLICY,
    STAGE_QUERY_EMBEDDING,
    STAGE_RETRIEVAL,
    STAGE_EVIDENCE_SUFFICIENCY,
    STAGE_PROMPT_CONSTRUCTION,
    STAGE_PROVIDER_GENERATION,
    STAGE_STRUCTURED_OUTPUT_PARSING,
    STAGE_GROUNDING_VERIFICATION,
    STAGE_CITATION_VALIDATION,
    STAGE_OUTPUT_SANITISATION,
    STAGE_PERSISTENCE,
    STAGE_RESPONSE_COMPLETED,
)


def new_trace_id() -> str:
    return f"trc_{uuid4()}"


@dataclass(frozen=True)
class AITraceContext:
    """Explicit, server-generated correlation identifiers threaded through one
    RAG request. Deliberately NOT contextvars-based: `RAGOrchestrator.answer()`
    is invoked from a `concurrent.futures.ThreadPoolExecutor` worker in
    `app.evaluation.engine`, and contextvars do not propagate into pool
    threads automatically - an ambient-context design would silently lose
    trace tagging for every evaluation-triggered RAG call.
    """

    trace_id: str
    request_id: str | None = None
    conversation_id: str | None = None
    eval_run_id: str | None = None
    eval_case_id: str | None = None

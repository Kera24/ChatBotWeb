from decimal import Decimal

from pydantic import BaseModel, Field

from app.ai.contracts import FinishReason, TokenUsage


class RAGAnswerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    model_key: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_key: str | None = Field(default=None, min_length=1, max_length=120)
    retrieval_limit: int | None = Field(default=None, ge=1, le=20)
    max_context_chars: int | None = Field(default=None, ge=1, le=50000)
    metadata: dict | None = None


class RAGCitationResponse(BaseModel):
    citation_index: int
    chunk_id: str
    document_id: str
    document_version_id: str
    source_title: str
    source_type: str
    page_number: int | None = None
    section_title: str | None = None
    similarity_score: float | None = None
    quoted_text: str | None = None


class RAGAnswerResponse(BaseModel):
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    answer: str
    answer_state: str
    citations: list[RAGCitationResponse]
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

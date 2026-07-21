from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ConversationCitationRead(BaseModel):
    id: str
    citation_index: int
    chunk_id: str
    document_id: str
    document_version_id: str
    similarity_score: Decimal | None = None
    source_title: str
    source_type: str
    page_number: int | None = None
    section_title: str | None = None
    quoted_text: str | None = None
    created_at: datetime


class ConversationMessageRead(BaseModel):
    id: str
    role: str
    content: str
    sequence_number: int
    answer_state: str | None = None
    model_key: str | None = None
    provider_key: str | None = None
    provider_model_name: str | None = None
    prompt_key: str | None = None
    prompt_version: int | None = None
    prompt_hash: str | None = None
    execution_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: Decimal | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None
    error_code: str | None = None
    created_at: datetime
    citations: list[ConversationCitationRead] = []


class ConversationSummaryRead(BaseModel):
    id: str
    organisation_id: str
    workspace_id: str
    channel: str
    status: str
    title: str | None = None
    started_at: datetime
    last_message_at: datetime | None = None
    ended_at: datetime | None = None
    message_count: int
    last_message_preview: str | None = None
    metadata: dict | None = None


class ConversationDetailRead(BaseModel):
    id: str
    organisation_id: str
    workspace_id: str
    channel: str
    status: str
    title: str | None = None
    started_at: datetime
    last_message_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict | None = None
    messages: list[ConversationMessageRead]

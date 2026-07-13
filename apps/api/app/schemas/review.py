from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.conversation import ConversationCitationRead, ConversationMessageRead


class ReviewItemRead(BaseModel):
    conversation_id: str
    assistant_message_id: str
    user_question: str | None = None
    assistant_answer: str
    answer_state: str
    error_code: str | None = None
    channel: str
    conversation_status: str
    model_key: str | None = None
    provider_key: str | None = None
    prompt_key: str | None = None
    prompt_version: int | None = None
    citation_count: int
    citations: list[ConversationCitationRead] = []
    created_at: datetime
    estimated_cost: Decimal | None = None
    latency_ms: int | None = None
    review_status: str
    reviewer_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


class ReviewItemDetailRead(BaseModel):
    item: ReviewItemRead
    conversation_context: list[ConversationMessageRead]


class ReviewStatusUpdate(BaseModel):
    review_status: str = Field(..., min_length=1, max_length=40)
    reviewer_note: str | None = Field(default=None, max_length=2000)

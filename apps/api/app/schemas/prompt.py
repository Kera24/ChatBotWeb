from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalCitation, RetrievalContextBlock


class RetrievalPromptRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=50)
    max_context_chars: int | None = Field(default=None, ge=1, le=100000)


class RetrievalPromptResponse(BaseModel):
    prompt_version: str
    system_prompt: str
    user_prompt: str
    context_blocks: list[RetrievalContextBlock]
    citations: list[RetrievalCitation]

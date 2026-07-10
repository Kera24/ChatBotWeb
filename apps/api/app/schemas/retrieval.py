from pydantic import BaseModel, Field


class RetrievalContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=50)
    max_context_chars: int | None = Field(default=None, ge=1, le=100000)


class RetrievalCitation(BaseModel):
    citation_index: int
    document_id: str
    document_version_id: str
    chunk_id: str
    source_title: str
    source_type: str
    page_number: int | None
    section_title: str | None
    score: float


class RetrievalContextBlock(RetrievalCitation):
    content: str
    context_text: str


class RetrievalContextResponse(BaseModel):
    query: str
    context_blocks: list[RetrievalContextBlock]
    citations: list[RetrievalCitation]
    total_context_chars: int

from pydantic import BaseModel, Field


class VectorSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=50)


class VectorSearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    score: float
    source_type: str
    source_title: str
    page_number: int | None
    section_title: str | None
    heading_path: str | None
    metadata_json: dict | None

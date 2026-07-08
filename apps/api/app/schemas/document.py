from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    source_type: str = Field(min_length=1, max_length=80)
    source_key: str | None = Field(default=None, max_length=512)
    category: str | None = Field(default=None, max_length=120)
    visibility: str = Field(default="workspace", min_length=1, max_length=40)
    metadata_json: dict[str, Any] | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    title: str
    source_type: str
    source_key: str | None
    status: str
    category: str | None
    visibility: str
    created_by_user_id: str | None
    active_document_version_id: str | None
    metadata_json: dict[str, Any] | None
    archived_at: datetime | None
    expires_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    document_id: str
    version_number: int
    original_file_path: str | None
    extracted_text_path: str | None
    checksum: str
    processing_status: str
    processing_error: str | None
    effective_from: datetime | None
    expires_at: datetime | None
    created_by_user_id: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organisation_id: str
    workspace_id: str
    document_id: str
    document_version_id: str
    chunk_index: int
    content: str
    content_hash: str
    token_count: int | None
    source_type: str
    source_title: str
    language: str | None
    chunking_strategy_version: str | None
    heading_path: str | None
    section_title: str | None
    page_number: int | None
    parser_name: str | None
    parser_version: str | None
    status: str
    metadata_json: dict[str, Any] | None
    embedding_model: str | None
    embedding_provider: str | None
    embedding_dimension: int | None
    embedding_created_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LifecycleTransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=40)
    error_message: str | None = Field(default=None, max_length=2000)

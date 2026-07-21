from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChatSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_chat_sessions_tenant_status", "organisation_id", "workspace_id", "status"),
        Index("ix_chat_sessions_recent", "organisation_id", "workspace_id", "last_message_at", "started_at"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active", server_default="active")
    anonymous_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    messages = relationship("ChatMessage", back_populates="conversation")
    citations = relationship("Citation", back_populates="conversation")


class ChatMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_number", name="uq_chat_messages_conversation_sequence"),
        Index("ix_chat_messages_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_chat_messages_conversation_order", "conversation_id", "sequence_number"),
        Index("ix_chat_messages_execution_id", "execution_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    answer_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider_model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    conversation = relationship("ChatSession", back_populates="messages")
    citations = relationship("Citation", back_populates="message")


class Citation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint("message_id", "citation_index", name="uq_citations_message_index"),
        Index("ix_citations_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_citations_message_order", "message_id", "citation_index"),
        Index("ix_citations_chunk", "chunk_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_messages.id"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(String(36), ForeignKey("chunks.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    document_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_versions.id"), nullable=False, index=True)
    citation_index: Mapped[int] = mapped_column(nullable=False)
    similarity_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    source_title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    conversation = relationship("ChatSession", back_populates="citations")
    message = relationship("ChatMessage", back_populates="citations")

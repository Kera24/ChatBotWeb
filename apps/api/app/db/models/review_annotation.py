from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewAnnotation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_annotations"
    __table_args__ = (
        UniqueConstraint("assistant_message_id", name="uq_review_annotations_assistant_message"),
        Index("ix_review_annotations_tenant_workspace", "organisation_id", "workspace_id"),
        Index("ix_review_annotations_status", "organisation_id", "workspace_id", "review_status"),
        Index("ix_review_annotations_message", "assistant_message_id"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id"), nullable=False, index=True)
    assistant_message_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_messages.id"), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", server_default="open")
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)

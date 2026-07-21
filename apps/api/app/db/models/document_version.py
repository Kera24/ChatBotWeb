from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version_number"),
        UniqueConstraint("organisation_id", "workspace_id", "document_id", "checksum", name="uq_document_versions_tenant_checksum"),
        Index("ix_document_versions_tenant_workspace_status", "organisation_id", "workspace_id", "processing_status"),
        Index("ix_document_versions_document_status", "document_id", "processing_status"),
    )

    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    original_file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    extracted_text_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", server_default="pending")
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document = relationship("Document", back_populates="versions", foreign_keys=[document_id])
    chunks = relationship("Chunk", back_populates="document_version")

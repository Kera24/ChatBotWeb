"""create document chunk schema

Revision ID: 0003_doc_chunk_schema
Revises: 0002_enable_pgvector_extension
Create Date: 2026-07-08
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import UserDefinedType


class PgVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self.dimensions})"


@compiles(PgVector, "sqlite")
def compile_pgvector_sqlite(type_: PgVector, compiler: object, **kw: object) -> str:
    return "TEXT"


@compiles(PgVector, "postgresql")
def compile_pgvector_postgresql(type_: PgVector, compiler: object, **kw: object) -> str:
    return f"vector({type_.dimensions})"


revision: str = "0003_doc_chunk_schema"
down_revision: str | None = "0002_enable_pgvector_extension"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="uploaded", nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("visibility", sa.String(length=40), server_default="workspace", nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("active_document_version_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organisation_id", "workspace_id", "source_type", "source_key", name="uq_documents_source_identity"),
    )
    op.create_index("ix_documents_organisation_id", "documents", ["organisation_id"])
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])
    op.create_index("ix_documents_tenant_workspace_status", "documents", ["organisation_id", "workspace_id", "status"])
    op.create_index("ix_documents_workspace_visibility_status", "documents", ["workspace_id", "visibility", "status"])

    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_file_path", sa.String(length=2048), nullable=True),
        sa.Column("extracted_text_path", sa.String(length=2048), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("processing_status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version_number"),
        sa.UniqueConstraint("organisation_id", "workspace_id", "document_id", "checksum", name="uq_document_versions_tenant_checksum"),
    )
    op.create_index("ix_document_versions_organisation_id", "document_versions", ["organisation_id"])
    op.create_index("ix_document_versions_workspace_id", "document_versions", ["workspace_id"])
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_tenant_workspace_status", "document_versions", ["organisation_id", "workspace_id", "processing_status"])
    op.create_index("ix_document_versions_document_status", "document_versions", ["document_id", "processing_status"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organisation_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_title", sa.String(length=512), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("chunking_strategy_version", sa.String(length=80), nullable=True),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("section_title", sa.String(length=512), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("parser_name", sa.String(length=120), nullable=True),
        sa.Column("parser_version", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("embedding_vector", PgVector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.Column("embedding_provider", sa.String(length=120), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"]),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_version_id", "chunk_index", name="uq_chunks_version_chunk_index"),
    )
    op.create_index("ix_chunks_organisation_id", "chunks", ["organisation_id"])
    op.create_index("ix_chunks_workspace_id", "chunks", ["workspace_id"])
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_document_version_id", "chunks", ["document_version_id"])
    op.create_index("ix_chunks_tenant_workspace_status", "chunks", ["organisation_id", "workspace_id", "status"])
    op.create_index("ix_chunks_document_version_status", "chunks", ["document_id", "document_version_id", "status"])
    op.create_index("ix_chunks_workspace_source_status", "chunks", ["workspace_id", "source_type", "status"])


def downgrade() -> None:
    op.drop_index("ix_chunks_workspace_source_status", table_name="chunks")
    op.drop_index("ix_chunks_document_version_status", table_name="chunks")
    op.drop_index("ix_chunks_tenant_workspace_status", table_name="chunks")
    op.drop_index("ix_chunks_document_version_id", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_index("ix_chunks_workspace_id", table_name="chunks")
    op.drop_index("ix_chunks_organisation_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_document_versions_document_status", table_name="document_versions")
    op.drop_index("ix_document_versions_tenant_workspace_status", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_index("ix_document_versions_workspace_id", table_name="document_versions")
    op.drop_index("ix_document_versions_organisation_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_workspace_visibility_status", table_name="documents")
    op.drop_index("ix_documents_tenant_workspace_status", table_name="documents")
    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_index("ix_documents_organisation_id", table_name="documents")
    op.drop_table("documents")

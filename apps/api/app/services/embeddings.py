from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from struct import unpack
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.models import Chunk, DocumentVersion
from app.repositories.audit_repository import add_audit_event
from app.repositories.document_repository import (
    get_document_version_for_workspace,
    list_chunks_for_document_version,
)


class EmbeddingTargetNotFound(LookupError):
    pass


class InvalidEmbeddingState(ValueError):
    pass


class EmbeddingProviderError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dimension: int

    def embed(self, text: str) -> list[float]:
        pass


@dataclass(frozen=True)
class EmbeddingResult:
    document_version: DocumentVersion
    success: bool
    embedded_chunk_count: int
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class LocalMockEmbeddingProvider:
    dimension: int
    provider_name: str = "local-mock"
    model_name: str = "local-mock-v1"

    def embed(self, text: str) -> list[float]:
        if self.dimension <= 0:
            raise EmbeddingProviderError("Embedding dimension must be positive.")

        digest = sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self.dimension:
            for offset in range(0, len(digest), 4):
                if len(values) >= self.dimension:
                    break
                integer = unpack(">I", digest[offset : offset + 4])[0]
                values.append((integer / 4294967295.0) * 2 - 1)
            digest = sha256(digest).digest()
        return values


@dataclass(frozen=True)
class FailingEmbeddingProvider:
    dimension: int
    provider_name: str = "failing-mock"
    model_name: str = "failing-mock-v1"

    def embed(self, text: str) -> list[float]:
        raise EmbeddingProviderError("Configured embedding provider failed.")


def build_embedding_provider(*, provider_name: str, model_name: str, dimension: int) -> EmbeddingProvider:
    if provider_name == "local-mock":
        return LocalMockEmbeddingProvider(dimension=dimension, model_name=model_name)
    if provider_name == "failing-mock":
        return FailingEmbeddingProvider(dimension=dimension, model_name=model_name)
    raise EmbeddingProviderError("Unsupported embedding provider.")


def embed_document_version_chunks(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    provider: EmbeddingProvider,
    actor_user_id: str | None = None,
) -> EmbeddingResult:
    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if version is None:
        raise EmbeddingTargetNotFound("Document version not found for tenant workspace.")

    if version.processing_status != "ready":
        raise InvalidEmbeddingState(
            f"Embedding requires processing_status 'ready', got {version.processing_status!r}."
        )

    chunks = list_chunks_for_document_version(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if not chunks:
        raise InvalidEmbeddingState("Embedding requires at least one ready chunk.")
    if any(chunk.status != "ready" for chunk in chunks):
        raise InvalidEmbeddingState("Embedding requires all chunks to be ready.")

    can_store_vector = db.bind is not None and db.bind.dialect.name == "postgresql"
    try:
        now = datetime.now(timezone.utc)
        for chunk in chunks:
            vector = provider.embed(chunk.content)
            if len(vector) != provider.dimension:
                raise EmbeddingProviderError("Embedding provider returned the wrong dimension.")
            if can_store_vector:
                chunk.embedding_vector = vector
            chunk.embedding_provider = provider.provider_name
            chunk.embedding_model = provider.model_name
            chunk.embedding_dimension = provider.dimension
            chunk.embedding_created_at = now
            metadata_json = dict(chunk.metadata_json or {})
            metadata_json["embedding"] = {
                "provider": provider.provider_name,
                "model": provider.model_name,
                "dimension": provider.dimension,
                "vector_stored": can_store_vector,
            }
            chunk.metadata_json = metadata_json
            db.add(chunk)
    except Exception:
        return _fail(
            db,
            version=version,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            actor_user_id=actor_user_id,
            error_code="EMBEDDING_PROVIDER_FAILED",
            error_message="Embedding provider failed safely.",
        )

    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.embedding.succeeded",
        entity_type="document_version",
        entity_id=version.id,
        document_id=document_id,
        document_version_id=version.id,
        previous_status=version.processing_status,
        new_status=version.processing_status,
        metadata_json={
            "embedded_chunk_count": len(chunks),
            "provider": provider.provider_name,
            "model": provider.model_name,
            "dimension": provider.dimension,
            "vector_stored": can_store_vector,
        },
    )
    db.commit()
    db.refresh(version)
    return EmbeddingResult(
        document_version=version,
        success=True,
        embedded_chunk_count=len(chunks),
    )


def _fail(
    db: Session,
    *,
    version: DocumentVersion,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    actor_user_id: str | None,
    error_code: str,
    error_message: str,
) -> EmbeddingResult:
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.embedding.failed",
        entity_type="document_version",
        entity_id=version.id,
        document_id=document_id,
        document_version_id=version.id,
        previous_status=version.processing_status,
        new_status=version.processing_status,
        metadata_json={"error_code": error_code},
    )
    db.commit()
    db.refresh(version)
    return EmbeddingResult(
        document_version=version,
        success=False,
        embedded_chunk_count=0,
        error_code=error_code,
        error_message=error_message,
    )

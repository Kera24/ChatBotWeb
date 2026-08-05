from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from struct import unpack
from typing import Protocol

import httpx
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


@dataclass(frozen=True)
class OllamaEmbeddingProvider:
    """A real, local, credential-free semantic embedding provider backed by a
    running Ollama instance. Unlike `LocalMockEmbeddingProvider` (a SHA-256
    hash with no semantic content), this produces vectors whose cosine
    similarity genuinely reflects text relevance - required for any retrieval
    similarity-threshold to be meaningful (see
    docs/04_Engineering/Evaluation_Real_Embedding_Provider.md).

    Deliberately has NO fallback to the mock provider on any failure -
    `embed()` always raises `EmbeddingProviderError` with an actionable
    message rather than silently degrading to hash-based vectors, since a
    caller who explicitly asked for real embeddings must never unknowingly
    get meaningless ones back.
    """

    dimension: int
    model_name: str
    base_url: str = "http://localhost:11434"
    provider_name: str = "ollama"
    timeout_seconds: float = 30.0

    def embed(self, text: str) -> list[float]:
        try:
            response = httpx.post(
                f"{self.base_url.rstrip('/')}/api/embed",
                json={"model": self.model_name, "input": text},
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise EmbeddingProviderError(
                f"Could not reach Ollama at {self.base_url!r} to embed text with model {self.model_name!r}: {exc}. "
                "Is the Ollama runtime running (`ollama serve`) and is EVAL_EMBEDDING_BASE_URL correct?"
            ) from exc
        if response.status_code != 200:
            raise EmbeddingProviderError(
                f"Ollama returned HTTP {response.status_code} embedding with model {self.model_name!r}: {response.text[:500]}. "
                f"Confirm the model is installed (`ollama pull {self.model_name}`) and supports embeddings."
            )
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not embeddings or not embeddings[0]:
            raise EmbeddingProviderError(f"Ollama returned no embedding vector for model {self.model_name!r}. Response: {payload!r}")
        vector = embeddings[0]
        if len(vector) != self.dimension:
            raise EmbeddingProviderError(
                f"Ollama model {self.model_name!r} returned a {len(vector)}-dimension vector, but this provider was "
                f"configured for dimension {self.dimension}. Set EVAL_EMBEDDING_DIMENSION to {len(vector)}, or verify "
                "you configured the model you intended."
            )
        return vector


def check_ollama_embedding_model_available(*, base_url: str, model_name: str, timeout_seconds: float = 5.0) -> None:
    """Fail clearly and immediately if the requested Ollama runtime/model is
    not available, rather than letting a real-embedding evaluation run
    silently fall back to nothing or fail deep inside a retrieval call with a
    confusing error. Raises EmbeddingProviderError with an actionable message
    on any problem; returns None (does nothing) when everything checks out."""
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EmbeddingProviderError(
            f"Could not reach Ollama at {base_url!r}: {exc}. Start it with `ollama serve` and confirm EVAL_EMBEDDING_BASE_URL."
        ) from exc

    models = response.json().get("models", [])

    def _matches(installed_name: str) -> bool:
        # Ollama model names are typically "name:tag" (e.g. "name:latest").
        # Accept either the fully-qualified name or the bare name so
        # EVAL_EMBEDDING_MODEL does not have to spell out ":latest".
        return installed_name == model_name or installed_name.split(":", 1)[0] == model_name

    matching = next((model for model in models if _matches(model.get("name", "")) or _matches(model.get("model", ""))), None)
    if matching is None:
        installed = sorted({model.get("name", model.get("model", "?")) for model in models})
        raise EmbeddingProviderError(
            f"Model {model_name!r} is not installed in the local Ollama runtime at {base_url!r}. "
            f"Installed models: {installed or '(none)'}. Install an embedding-capable model with `ollama pull {model_name}`, "
            "or set EVAL_EMBEDDING_MODEL to one of the installed models above."
        )
    capabilities = matching.get("capabilities", [])
    if capabilities and "embedding" not in capabilities:
        raise EmbeddingProviderError(
            f"Model {model_name!r} is installed but does not report an 'embedding' capability "
            f"(capabilities: {capabilities}). Choose a dedicated embedding model instead."
        )


def build_embedding_provider(*, provider_name: str, model_name: str, dimension: int, base_url: str | None = None) -> EmbeddingProvider:
    if provider_name == "local-mock":
        return LocalMockEmbeddingProvider(dimension=dimension, model_name=model_name)
    if provider_name == "failing-mock":
        return FailingEmbeddingProvider(dimension=dimension, model_name=model_name)
    if provider_name == "ollama":
        if not model_name:
            raise EmbeddingProviderError(
                "provider_name='ollama' requires an explicit model_name (set EVAL_EMBEDDING_MODEL) - "
                "no default model is assumed, since which models are installed varies by machine."
            )
        return OllamaEmbeddingProvider(dimension=dimension, model_name=model_name, base_url=base_url or "http://localhost:11434")
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

from dataclasses import dataclass
from math import sqrt

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentVersion
from app.services.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class VectorSearchMatch:
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


def search_embedded_chunks(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    limit: int,
    provider: EmbeddingProvider,
    document_ids: list[str] | None = None,
    min_similarity_score: float = 0.0,
) -> list[VectorSearchMatch]:
    # `document_ids=None` means "no scope restriction requested" (e.g. a raw
    # workspace-level dashboard-test query with no assistant selected) and
    # correctly falls through to an unfiltered search below. `document_ids=[]`
    # means an assistant WAS resolved and its configured knowledge scope is
    # explicitly empty - every widget defaults to `knowledge_scope_json=[]`
    # until an admin attaches documents (see
    # app.access.widget_admin.service.create_widget and the "may use fallback
    # answers until scope is configured" warning surfaced in the admin UI).
    # Without this guard, `if document_ids:` / `not bool(document_ids)` checks
    # in the two backend-specific search functions below both treat `[]` the
    # same as `None` and silently return every workspace document - meaning
    # any newly created, not-yet-configured assistant could answer from any
    # other assistant's documents in the same workspace. An explicitly empty
    # scope must always retrieve zero chunks, never "everything".
    if document_ids is not None and len(document_ids) == 0:
        return []

    query_vector = provider.embed(query)
    if len(query_vector) != provider.dimension:
        raise ValueError("Embedding provider returned the wrong dimension.")

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        matches = _search_postgresql(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query_vector=query_vector,
            provider=provider,
            limit=limit,
            document_ids=document_ids,
        )
    else:
        matches = _search_sqlite(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query_vector=query_vector,
            provider=provider,
            limit=limit,
            document_ids=document_ids,
        )

    # Applied uniformly across both backends here (rather than duplicated in
    # each backend's own SQL) so the threshold semantics are identical
    # regardless of dialect. A match's `score` is already the same
    # cosine-similarity number in both backends. Filtering after the
    # backend's own top-`limit` selection is safe: since results are always
    # ordered by descending score, no higher-scored match beyond the returned
    # set exists to miss.
    if min_similarity_score > 0.0:
        matches = [match for match in matches if match.score >= min_similarity_score]
    return matches


def _search_sqlite(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query_vector: list[float],
    provider: EmbeddingProvider,
    limit: int,
    document_ids: list[str] | None = None,
) -> list[VectorSearchMatch]:
    statement = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            Chunk.organisation_id == organisation_id,
            Chunk.workspace_id == workspace_id,
            Chunk.status == "ready",
            Chunk.embedding_created_at.is_not(None),
            Chunk.embedding_provider == provider.provider_name,
            Chunk.embedding_model == provider.model_name,
            Chunk.embedding_dimension == provider.dimension,
            Document.organisation_id == organisation_id,
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            Document.active_document_version_id == Chunk.document_version_id,
            DocumentVersion.organisation_id == organisation_id,
            DocumentVersion.workspace_id == workspace_id,
            DocumentVersion.id == Chunk.document_version_id,
            DocumentVersion.processing_status == "ready",
        )
    )
    if document_ids:
        statement = statement.where(Chunk.document_id.in_(document_ids))
    chunks = list(db.execute(statement).scalars().all())
    matches = [
        _match_from_chunk(
            chunk,
            score=_cosine_similarity(query_vector, provider.embed(chunk.content)),
        )
        for chunk in chunks
    ]
    matches.sort(key=lambda item: (-item.score, item.chunk_index, item.chunk_id))
    return matches[:limit]


def _search_postgresql(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query_vector: list[float],
    provider: EmbeddingProvider,
    limit: int,
    document_ids: list[str] | None = None,
) -> list[VectorSearchMatch]:
    query_vector_literal = "[" + ",".join(str(value) for value in query_vector) + "]"
    statement = text(
        """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.document_version_id,
            c.chunk_index,
            c.content,
            1 - (c.embedding_vector <=> CAST(:query_vector AS vector)) AS score,
            c.source_type,
            c.source_title,
            c.page_number,
            c.section_title,
            c.heading_path,
            c.metadata_json
        FROM chunks AS c
        JOIN documents AS d ON d.id = c.document_id
        JOIN document_versions AS dv ON dv.id = c.document_version_id
        WHERE c.organisation_id = :organisation_id
          AND c.workspace_id = :workspace_id
          AND c.status = 'ready'
          AND c.embedding_vector IS NOT NULL
          AND c.embedding_created_at IS NOT NULL
          AND c.embedding_provider = :provider_name
          AND c.embedding_model = :model_name
          AND c.embedding_dimension = :dimension
          AND d.organisation_id = :organisation_id
          AND d.workspace_id = :workspace_id
          AND d.deleted_at IS NULL
          AND d.active_document_version_id = c.document_version_id
          AND dv.organisation_id = :organisation_id
          AND dv.workspace_id = :workspace_id
          AND dv.id = c.document_version_id
          AND dv.processing_status = 'ready'
          AND (:document_ids_empty = true OR c.document_id IN :document_ids)
        ORDER BY c.embedding_vector <=> CAST(:query_vector AS vector), c.chunk_index, c.id
        LIMIT :limit
        """
    ).bindparams(bindparam("document_ids", expanding=True))
    rows = db.execute(
        statement,
        {
            "organisation_id": organisation_id,
            "workspace_id": workspace_id,
            "query_vector": query_vector_literal,
            "provider_name": provider.provider_name,
            "model_name": provider.model_name,
            "dimension": provider.dimension,
            "limit": limit,
            "document_ids_empty": not bool(document_ids),
            "document_ids": document_ids or ["__none__"],
        },
    ).mappings()
    return [VectorSearchMatch(**dict(row)) for row in rows]


def _match_from_chunk(chunk: Chunk, *, score: float) -> VectorSearchMatch:
    return VectorSearchMatch(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_version_id=chunk.document_version_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        score=score,
        source_type=chunk.source_type,
        source_title=chunk.source_title,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        heading_path=chunk.heading_path,
        metadata_json=chunk.metadata_json,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)
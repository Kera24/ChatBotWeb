"""Lexical (keyword/full-text) retrieval - the second candidate-generation
channel for Retrieval V2 Phase 1 hybrid retrieval (see
docs/future/HybridRetrieval.md, docs/sops/adding-hybrid-retrieval.md).

Deliberately mirrors app.services.vector_search's interface and filtering
shape (same dataclass fields, same document_ids None-vs-[] semantics, same
tenant/workspace/ready-status/active-version WHERE clauses) so the two
channels are trivially comparable and fusable by app.services.retrieval_fusion.

Postgres uses native full-text search (to_tsvector/websearch_to_tsquery/
ts_rank_cd) via a GIN index (see the lexical_search_index migration).
SQLite has no full-text search engine available in this stack, so it uses a
deterministic Python term-overlap fallback over the same filtered candidate
set _search_sqlite already fetches - not semantically equivalent to real
BM25/tsvector ranking, but sufficient for dev/test determinism (see
docs/architecture/vector-storage.md's existing SQLite-vs-Postgres divergence
precedent for _search_sqlite/_search_postgresql).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentVersion

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class LexicalSearchMatch:
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


def search_lexical_chunks(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    limit: int,
    document_ids: list[str] | None = None,
) -> list[LexicalSearchMatch]:
    # Same knowledge-scope guard as app.services.vector_search.search_embedded_chunks
    # (see that function's docstring comment for the full rationale):
    # document_ids=None means "no scope restriction requested"; document_ids=[]
    # means an assistant resolved to an explicitly empty scope and must
    # retrieve zero chunks, never fall back to "everything".
    if document_ids is not None and len(document_ids) == 0:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _search_postgresql(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            query=query,
            limit=limit,
            document_ids=document_ids,
        )
    return _search_sqlite(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        tokens=tokens,
        limit=limit,
        document_ids=document_ids,
    )


def _tokenize(query: str) -> list[str]:
    return _TOKEN_PATTERN.findall(query.lower())


def _search_sqlite(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    tokens: list[str],
    limit: int,
    document_ids: list[str] | None = None,
) -> list[LexicalSearchMatch]:
    statement = (
        select(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            Chunk.organisation_id == organisation_id,
            Chunk.workspace_id == workspace_id,
            Chunk.status == "ready",
            Document.organisation_id == organisation_id,
            Document.workspace_id == workspace_id,
            Document.deleted_at.is_(None),
            # Same "ready" invariant as _search_sqlite in vector_search.py -
            # archived/expired/processing/failed documents never retrievable.
            Document.status == "ready",
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

    matches: list[LexicalSearchMatch] = []
    unique_tokens = set(tokens)
    for chunk in chunks:
        content_tokens = set(_tokenize(chunk.content))
        hits = len(unique_tokens & content_tokens)
        if hits == 0:
            continue
        score = hits / len(unique_tokens)
        matches.append(_match_from_chunk(chunk, score=score))

    matches.sort(key=lambda item: (-item.score, item.chunk_index, item.chunk_id))
    return matches[:limit]


def _search_postgresql(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    limit: int,
    document_ids: list[str] | None = None,
) -> list[LexicalSearchMatch]:
    statement = text(
        """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.document_version_id,
            c.chunk_index,
            c.content,
            ts_rank_cd(to_tsvector('english', c.content), websearch_to_tsquery('english', :query)) AS score,
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
          AND d.organisation_id = :organisation_id
          AND d.workspace_id = :workspace_id
          AND d.deleted_at IS NULL
          AND d.status = 'ready'
          AND d.active_document_version_id = c.document_version_id
          AND dv.organisation_id = :organisation_id
          AND dv.workspace_id = :workspace_id
          AND dv.id = c.document_version_id
          AND dv.processing_status = 'ready'
          AND (:document_ids_empty = true OR c.document_id IN :document_ids)
          AND to_tsvector('english', c.content) @@ websearch_to_tsquery('english', :query)
        ORDER BY score DESC, c.chunk_index, c.id
        LIMIT :limit
        """
    ).bindparams(bindparam("document_ids", expanding=True))
    rows = db.execute(
        statement,
        {
            "organisation_id": organisation_id,
            "workspace_id": workspace_id,
            "query": query,
            "limit": limit,
            "document_ids_empty": not bool(document_ids),
            "document_ids": document_ids or ["__none__"],
        },
    ).mappings()
    return [LexicalSearchMatch(**dict(row)) for row in rows]


def _match_from_chunk(chunk: Chunk, *, score: float) -> LexicalSearchMatch:
    return LexicalSearchMatch(
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

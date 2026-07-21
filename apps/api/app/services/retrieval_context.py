from dataclasses import dataclass

from app.services.embeddings import EmbeddingProvider
from app.services.vector_search import VectorSearchMatch, search_embedded_chunks
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class RetrievalCitationData:
    citation_index: int
    document_id: str
    document_version_id: str
    chunk_id: str
    source_title: str
    source_type: str
    page_number: int | None
    section_title: str | None
    score: float


@dataclass(frozen=True)
class RetrievalContextBlockData(RetrievalCitationData):
    content: str
    context_text: str


@dataclass(frozen=True)
class RetrievalContextResult:
    query: str
    context_blocks: list[RetrievalContextBlockData]
    citations: list[RetrievalCitationData]
    total_context_chars: int


def assemble_retrieval_context(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    query: str,
    search_limit: int,
    max_context_chunks: int,
    max_context_chars: int,
    provider: EmbeddingProvider,
    document_ids: list[str] | None = None,
) -> RetrievalContextResult:
    effective_limit = min(search_limit, max_context_chunks)
    matches = search_embedded_chunks(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        query=query,
        limit=effective_limit,
        provider=provider,
        document_ids=document_ids,
    )
    return assemble_context_from_matches(
        query=query,
        matches=matches,
        max_context_chunks=max_context_chunks,
        max_context_chars=max_context_chars,
    )


def assemble_context_from_matches(
    *,
    query: str,
    matches: list[VectorSearchMatch],
    max_context_chunks: int,
    max_context_chars: int,
) -> RetrievalContextResult:
    if max_context_chunks <= 0:
        raise ValueError("max_context_chunks must be positive.")
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive.")

    context_blocks: list[RetrievalContextBlockData] = []
    citations: list[RetrievalCitationData] = []
    total_context_chars = 0

    for match in matches[:max_context_chunks]:
        citation_index = len(context_blocks) + 1
        prefix = _context_prefix(citation_index, match)
        remaining_chars = max_context_chars - total_context_chars
        if remaining_chars <= len(prefix):
            break

        content = match.content[: remaining_chars - len(prefix)]
        if not content:
            break
        context_text = prefix + content
        citation = RetrievalCitationData(
            citation_index=citation_index,
            document_id=match.document_id,
            document_version_id=match.document_version_id,
            chunk_id=match.chunk_id,
            source_title=match.source_title,
            source_type=match.source_type,
            page_number=match.page_number,
            section_title=match.section_title,
            score=match.score,
        )
        context_blocks.append(
            RetrievalContextBlockData(
                **citation.__dict__,
                content=content,
                context_text=context_text,
            )
        )
        citations.append(citation)
        total_context_chars += len(context_text)
        if total_context_chars >= max_context_chars:
            break

    return RetrievalContextResult(
        query=query,
        context_blocks=context_blocks,
        citations=citations,
        total_context_chars=total_context_chars,
    )


def _context_prefix(citation_index: int, match: VectorSearchMatch) -> str:
    source_parts = [match.source_title]
    if match.section_title:
        source_parts.append(match.section_title)
    if match.page_number is not None:
        source_parts.append(f"page {match.page_number}")
    return f"[{citation_index}] {' | '.join(source_parts)}\n"

"""Layer F: citation enforcement.

By construction, `RAGOrchestrator` only ever builds a citation from a chunk
`assemble_retrieval_context` actually returned - which is itself already
scoped to the assistant's authorised documents and to the tenant's
organisation/workspace at the SQL query level (see
app.services.vector_search._search_sqlite/_search_postgresql, which filter on
`Document.deleted_at.is_(None)` and `Document.active_document_version_id`, so
an archived/inactive document's chunks are never retrieved in the first
place). There is no code path today where a citation is parsed out of free
text and could be spoofed.

This module is the explicit, defense-in-depth *assertion* of that invariant
at the point citations are about to be persisted - a belt-and-suspenders
runtime check, not a new filtering mechanism. If it ever fires, that means a
retrieval-scoping bug was introduced elsewhere and citations were about to
leak outside the assistant's authorised scope; treating that as a hard
failure (never a silently-dropped citation) is deliberate, since silently
continuing would hide a real defect instead of surfacing it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.guardrails.reason_codes import GuardrailReasonCode
from app.services.retrieval_context import RetrievalCitationData

SAFE_MESSAGE_CITATION_INVALID = "The available knowledge base does not contain enough verified information to answer that."


@dataclass(frozen=True)
class CitationPolicyVerdict:
    passed: bool
    reason_code: GuardrailReasonCode
    invalid_citation_ids: tuple[str, ...] = ()
    safe_message: str | None = None


def verify_citations(citations: list[RetrievalCitationData], *, allowed_document_ids: list[str] | None) -> CitationPolicyVerdict:
    """`allowed_document_ids=None` means no scope restriction was requested
    for this call (matches the existing semantics in
    app.services.vector_search.search_embedded_chunks - see its own
    docstring) - every citation is trivially in-scope in that case."""
    if allowed_document_ids is None:
        return CitationPolicyVerdict(passed=True, reason_code=GuardrailReasonCode.OUTPUT_SAFE)

    allowed = set(allowed_document_ids)
    invalid = tuple(citation.chunk_id for citation in citations if citation.document_id not in allowed)
    if invalid:
        return CitationPolicyVerdict(
            passed=False, reason_code=GuardrailReasonCode.CITATION_FOREIGN_SCOPE,
            invalid_citation_ids=invalid, safe_message=SAFE_MESSAGE_CITATION_INVALID,
        )
    return CitationPolicyVerdict(passed=True, reason_code=GuardrailReasonCode.OUTPUT_SAFE)

# Epic: Knowledge Management and RAG

## Epic ID

EPIC-003

## Status

Draft

## Problem

Clients need to update knowledge frequently without developer involvement, and the chatbot must answer using only approved active knowledge.

## Goal

Build the knowledge ingestion and RAG foundation for document upload, processing, retrieval, grounded answering, and citations.

## Users

- Client admin
- Knowledge contributor
- Public chatbot user

## Scope

- Document upload
- FAQ management
- Document lifecycle states
- Text extraction
- Chunking
- Embeddings
- Tenant-aware retrieval
- Answer generation
- Citations
- Safe fallback

## Out of scope

- SharePoint sync
- Google Drive sync
- Website crawler
- Advanced agent tools

## Requirements

- Client admins can upload supported documents.
- Documents process asynchronously.
- Chunks include source metadata.
- Retrieval is workspace-scoped.
- Answers include citations where evidence exists.
- The chatbot falls back safely when evidence is weak.

## Acceptance criteria

- [ ] PDF, DOCX, TXT, and CSV are accepted.
- [ ] Document status is visible.
- [ ] Ready documents become searchable.
- [ ] Archived or expired documents are excluded.
- [ ] Chat answers use only tenant-scoped chunks.
- [ ] Low-confidence answers are flagged.

## Dependencies

- EPIC-001
- EPIC-002
- docs/03_AI/01_RAG_Architecture.md

## Risks

- Poor extraction quality
- Poor retrieval quality
- Hallucinated answers
- High AI cost

## Implementation notes

Begin with a simple RAG pipeline and add hybrid search, reranking, and evaluation after the MVP works end-to-end.

# RAG Implementation Standards

Version: 1.0
Status: Active Draft

## 1. AI platform goal

The AI layer must allow each tenant workspace to answer questions from its own approved knowledge sources with strong source grounding, safe fallback behaviour, and measurable quality.

## 2. MVP RAG scope

MVP includes:

- Document text extraction
- Chunking
- Embedding generation
- Vector storage
- Tenant-aware retrieval
- Context assembly
- Answer generation
- Source citations
- Safe fallback

MVP excludes:

- Advanced autonomous agents
- SharePoint sync
- Google Drive sync
- Website crawler
- Fine-tuning
- Complex memory

## 3. Ingestion pipeline

```text
Upload
  -> Validate
  -> Store original file
  -> Extract text
  -> Clean text
  -> Chunk text
  -> Attach metadata
  -> Generate embeddings
  -> Store vectors
  -> Mark ready
```

## 4. Query pipeline

```text
Question
  -> Resolve workspace
  -> Validate public or authenticated access
  -> Retrieve active tenant-scoped chunks
  -> Rank results
  -> Assemble context
  -> Generate answer
  -> Attach citations
  -> Log usage
  -> Return answer or fallback
```

## 5. Chunking rules

Initial defaults:

- Chunk size: 600 to 1000 tokens
- Overlap: 100 to 150 tokens
- Preserve source title
- Preserve page or section where available
- Preserve document version

Chunking must be adjustable after evaluation.

## 6. Metadata requirements

Each chunk must include:

- organisation_id
- workspace_id
- document_id
- document_version_id
- source_type
- source_title
- section_title where available
- page_number where available
- status
- effective_from
- expires_at

## 7. Retrieval rules

Retrieval must always filter by:

- organisation_id
- workspace_id
- active chunk status
- active document status
- non-expired document state

Never retrieve from vector storage without tenant metadata filters.

## 8. Answer rules

The assistant must:

1. Use only retrieved context.
2. Avoid guessing.
3. Cite sources when possible.
4. Say when knowledge is unavailable.
5. Ask clarification when user intent is vague.
6. Log low-confidence or fallback responses.

## 9. Prompt rules

Prompts must be versioned and stored in `packages/prompts` or equivalent.

Prompts should include:

- Role
- Task
- Context
- Answer rules
- Refusal rules
- Citation rules
- Tone rules

## 10. Evaluation rules

RAG quality must eventually be evaluated using:

- Golden questions
- Retrieval relevance
- Answer faithfulness
- Citation correctness
- Fallback correctness
- Latency
- Cost

## 11. Cost controls

The AI layer should support:

- Usage logging
- Token tracking
- Model configuration
- Rate limiting
- Caching in future
- Per-tenant cost reporting

## 12. Safety and security

Risks to protect against:

- Prompt injection in uploaded documents
- Prompt injection in user questions
- Cross-tenant retrieval
- Leaking system prompts
- Hallucinated answers
- Answering from expired documents

## 13. Immediate RAG implementation sequence

1. Define document and chunk models.
2. Implement upload and status tracking.
3. Implement text extraction.
4. Implement chunking.
5. Implement embeddings abstraction.
6. Implement tenant-filtered retrieval.
7. Implement answer generation with citations.
8. Implement fallback and unanswered question tracking.

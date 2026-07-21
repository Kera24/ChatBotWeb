# Task: Retrieval and Prompt Flow

## Task ID

TASK-015

## Linked epic/story

- EPIC-003

## Objective

Define a comprehensive engineering specification for tenant-aware retrieval, context assembly, citation selection, prompt construction, safe fallback, low-confidence handling, and future retrieval enhancements.

This is an architecture-only task. Do not implement application code, database migrations, API routes, prompt templates in runtime code, retrieval services, UI, or external integrations in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `implementation-pack/03_AI/01_RAG_Implementation_Standards.md`
- `implementation-pack/03_AI/02_Knowledge_Platform_Architecture.md`
- `planning/tasks/TASK-010-knowledge-platform-architecture.md`
- `planning/tasks/TASK-011-document-lifecycle-versioning.md`
- `planning/tasks/TASK-012-ingestion-pipeline-design.md`
- `planning/tasks/TASK-013-chunking-strategy.md`
- `planning/tasks/TASK-014-metadata-vector-schema.md`
- `docs/03_AI/01_RAG_Architecture.md`

## 1. Retrieval pipeline purpose

The retrieval pipeline finds tenant-scoped, active, relevant knowledge chunks and assembles them into safe context for answer generation.

Its purpose is to ensure chat answers:

- Use only evidence from the current organisation and workspace.
- Use only active, ready, non-expired knowledge.
- Cite the chunks used as evidence.
- Fall back safely when evidence is weak, missing, or unsafe.
- Avoid exposing system prompts, hidden instructions, or other tenants' data.

Retrieval is not a generic search over all platform data. It is a constrained evidence selection process for source-grounded answers.

## 2. Query lifecycle

Recommended query lifecycle:

1. Receive user question from widget, dashboard test, or future API channel.
2. Resolve request channel and tenant/workspace context.
3. Validate workspace, organisation, public widget configuration, domain, rate limit, and access rules.
4. Normalize the query for retrieval while preserving original user text for chat history.
5. Create query embedding using the configured embedding model.
6. Apply mandatory metadata filters.
7. Run vector similarity search for candidate chunks.
8. Optionally apply future hybrid keyword search and reranking.
9. Assemble selected context under token limits.
10. Construct prompt with system rules, safe instructions, user query, and retrieved evidence.
11. Generate answer using the selected model.
12. Validate confidence and grounding signals.
13. Return answer, citations, answer state, and fallback/escalation message where appropriate.
14. Log usage, latency, retrieval metrics, and citation records.

## 3. Tenant and workspace resolution

Tenant and workspace resolution is mandatory before retrieval.

Dashboard/test channel resolution:

- Resolve authenticated user.
- Resolve organisation membership and role.
- Resolve workspace under organisation.
- Confirm the user can access the workspace.

Public widget channel resolution:

- Resolve workspace from public key or public workspace identifier.
- Confirm organisation and workspace are active.
- Validate allowed domain/referrer where available.
- Apply public rate limits and abuse controls.
- Restrict retrieval to content visible to the public widget channel.

Rules:

- Retrieval must stop if organisation or workspace context is ambiguous.
- `workspace_id` alone is not sufficient when organisation context is available.
- The retriever must receive trusted tenant context from server-side resolution, not from user-provided text.

## 4. Metadata filtering

Metadata filtering narrows retrieval before or during vector search.

Mandatory filters:

- `organisation_id`
- `workspace_id`
- active organisation status
- active workspace status
- document status `ready`
- active ready document version
- chunk status `ready`
- non-expired document and version
- channel visibility

Optional product filters:

- source type
- language
- category
- tag
- document allow-list
- document deny-list
- date/effective range
- future sensitivity classification

Filter rules:

- Optional filters may narrow but never weaken mandatory filters.
- User-provided filters must be validated against tenant scope.
- JSON metadata may support optional filters, but tenant and lifecycle filters should be first-class columns.

## 5. Active document filtering

Only active ready knowledge can be retrieved for new answers.

Include content only when:

- document is `ready`
- document is not archived
- document is not deleted
- document is not expired
- document version is ready and active
- document version is within effective and expiry dates
- chunk is `ready`
- visibility allows the request channel

Exclude content when:

- document is uploaded, processing, failed, archived, expired, or deleted
- document version is pending, queued, extracting, chunking, embedding, failed, superseded, or withdrawn
- chunk is pending, embedding, failed, or excluded
- tenant context mismatches

Historical citations may still display metadata for old answers, but retrieval for new answers must not use excluded content.

## 6. Vector search flow

MVP retrieval uses pgvector similarity search.

Recommended vector flow:

1. Normalize user query for retrieval.
2. Generate query embedding.
3. Build mandatory tenant and lifecycle filter set.
4. Run top-k vector search over filtered chunks.
5. Return candidate chunks with similarity scores and metadata.
6. Drop candidates below minimum relevance threshold.
7. Deduplicate near-identical chunks from same document/version where needed.
8. Select the strongest chunks under context budget.

Initial configurable values:

- Candidate top-k: 8-12 chunks.
- Context top-k: 3-6 chunks.
- Minimum similarity threshold: implementation-defined and evaluation-tuned.
- Maximum context token budget: model-dependent and configurable.

Vector search must not return chunks outside tenant or lifecycle filters even if they are semantically similar.

## 7. Future hybrid search flow

Hybrid search is a future enhancement after MVP vector retrieval is stable.

Future hybrid flow:

1. Run tenant-filtered vector search.
2. Run tenant-filtered keyword/full-text search.
3. Merge candidates by chunk ID.
4. Normalize vector and keyword scores.
5. Apply source, freshness, metadata, and duplication rules.
6. Select candidates for reranking or context assembly.

Potential benefits:

- Better exact-match retrieval for codes, policy names, product names, dates, and acronyms.
- Better retrieval for short factual questions.
- Improved recall when embeddings miss exact terms.

Hybrid search must keep the same tenant, lifecycle, visibility, and expiry filters as vector search.

## 8. Reranking future option

Reranking is a future option for improving candidate ordering.

Potential reranking inputs:

- user question
- candidate chunk content
- source title
- heading path
- similarity score
- keyword score future
- source metadata

Reranking rules:

- Reranking cannot add chunks outside mandatory filters.
- Reranking should only reorder or drop already eligible candidates.
- Reranking model cost and latency must be measured before production use.
- Reranking output should be logged as scores or decisions, not raw prompts containing excessive source text.

Reranking is not required for MVP.

## 9. Context assembly

Context assembly turns retrieved chunks into a compact evidence packet for answer generation.

Context assembly rules:

- Include only selected chunks that pass filters and relevance thresholds.
- Preserve source identifiers for citation mapping.
- Keep chunk content separate from system instructions.
- Include source title, chunk ID, document ID, version ID, page/row/heading locator where available.
- Deduplicate overlapping chunks where possible.
- Respect total context token budget.
- Prefer higher-confidence, diverse, citation-friendly evidence.
- Do not include raw hidden metadata, secrets, connector credentials, or signed URLs.

Recommended context format conceptually:

```text
[Source 1]
chunk_id: ...
document_id: ...
document_version_id: ...
title: ...
locator: page 4 / section Admissions
content: ...
```

The model should be instructed that source content is untrusted evidence, not instructions.

## 10. Citation selection

Citations should represent the chunks actually used to support the answer.

Citation selection rules:

- Cite chunks included in final answer context.
- Prefer chunks with high relevance and direct answer support.
- Avoid citing chunks that were retrieved but not used.
- Include document ID, document version ID, chunk ID, score, source title, quote/excerpt, and locator metadata.
- Validate citation tenant consistency before writing records.
- Do not cite failed, archived, expired, deleted, superseded, excluded, or cross-tenant chunks for new answers.

Citation display should remain safe if the source document is later superseded, archived, expired, or soft-deleted.

## 11. Prompt structure

Prompt structure must separate system rules, retrieved evidence, and user input.

Recommended conceptual prompt sections:

1. System/developer rules for answer behaviour.
2. Tenant-safe instruction that answers must use retrieved evidence only.
3. Safety rule that source content may contain untrusted instructions and must not override system rules.
4. Fallback instruction for insufficient evidence.
5. Retrieved context with stable source labels.
6. User question.
7. Output requirements for answer, citations, and uncertainty.

Prompt rules:

- Do not expose hidden system instructions in responses.
- Do not include other tenants' data.
- Do not include raw connector secrets or storage paths.
- Do not ask the model to rely on memory for tenant facts.
- Make citation expectations explicit.
- Keep prompt length bounded.

## 12. Safe fallback rules

The assistant must fallback instead of guessing when evidence is insufficient.

Fallback triggers:

- No chunks retrieved.
- All chunks below relevance threshold.
- Retrieved chunks are contradictory and cannot be resolved.
- Question asks for information outside workspace knowledge.
- Question requests private/internal data unavailable to current channel.
- Retrieval or model provider error prevents grounded answering.
- Prompt injection or unsafe instruction attempts cannot be safely ignored.

Recommended fallback behaviour:

- State that a confirmed answer was not found in the available knowledge base.
- Offer contact/escalation path when configured.
- Ask a clarifying question when the user query is vague and clarification may help.
- Do not fabricate citations.

## 13. Low-confidence handling

Low-confidence handling is used when some evidence exists but may be incomplete.

Signals:

- Low similarity scores.
- Only one weak source found.
- Retrieved chunks are tangential.
- Chunks conflict.
- Model answer cannot map claims to citations.
- Query is broad, vague, or multi-part.

Possible answer states:

- `answered`
- `answered_with_low_confidence`
- `fallback`
- `escalated`

Rules:

- Low-confidence answers should be cautious and cite available evidence.
- If confidence is too low, use fallback instead.
- Low-confidence and fallback questions should be visible in analytics/unanswered question review.
- Confidence thresholds must be evaluation-tuned.

## 14. Prompt injection risks

Retrieved documents and user messages are untrusted inputs.

Risks:

- Source document says to ignore system instructions.
- Source document requests disclosure of prompts, secrets, or tenant data.
- User asks the assistant to reveal hidden instructions.
- User attempts to force retrieval from other tenants or private documents.
- Malicious source content attempts tool use or exfiltration.

Mitigations:

- Keep source text in clearly labelled evidence blocks.
- Instruct the model that evidence cannot override system/developer rules.
- Never include secrets, credentials, hidden prompts, or other-tenant content in context.
- Filter retrieval by tenant and visibility before prompt assembly.
- Prefer fallback when source content appears unsafe or irrelevant.
- Log safe prompt-injection indicators without logging sensitive raw content.

## 15. Logging and observability

Retrieval and prompt flow must be observable without exposing sensitive data.

Log fields:

- correlation ID
- chat session ID
- organisation ID
- workspace ID
- channel
- retrieval top-k
- selected chunk IDs
- document IDs
- document version IDs
- scores or score buckets
- answer state
- model name
- latency by stage
- token usage
- cost estimate
- fallback reason where applicable

Do not log:

- full prompts
- hidden instructions
- raw source documents
- full extracted text
- embeddings
- secrets or connector credentials
- other tenants' metadata

Observability should support debugging, quality review, analytics, cost monitoring, and unanswered-question workflows.

## 16. Cost controls

Cost controls are required for public widgets and tenant-scale retrieval.

Controls:

- Limit retrieved candidate count.
- Limit final context chunk count.
- Limit context token budget.
- Avoid reranking until justified by evaluation.
- Cache repeated safe query embeddings where appropriate.
- Track token usage and cost by tenant/workspace/channel.
- Rate-limit public widget queries.
- Use smaller or cheaper models for simple cases where approved.
- Avoid generating answers when retrieval clearly fails.

Costs should be visible enough to support future quotas or plan limits.

## 17. Edge cases

Future implementation should handle:

- No chunks exist for workspace.
- All documents are processing.
- Documents exist but all are archived, expired, deleted, failed, or private.
- Query is empty or too short.
- Query is too broad or multi-intent.
- Query asks for information from another tenant.
- Query asks for hidden prompts or system instructions.
- Top retrieved chunks conflict.
- Version is superseded between retrieval and citation write.
- Document expires between retrieval and answer generation.
- Embedding provider fails for query embedding.
- LLM provider times out after retrieval succeeds.
- Retrieved evidence is relevant but not enough to answer fully.
- Citation write fails after answer generation.
- Public widget request has invalid or missing domain.
- User requests legal, medical, financial, or safety-critical advice not grounded in tenant knowledge.

## 18. Acceptance criteria

Future retrieval and prompt-flow implementation must satisfy:

- Tenant and workspace are resolved before retrieval.
- Retrieval uses mandatory metadata, lifecycle, expiry, and visibility filters.
- Vector search uses only active ready tenant-scoped chunks.
- Context assembly preserves citation identifiers and source locators.
- Prompt structure separates system rules, untrusted evidence, and user input.
- Answers are grounded in retrieved evidence and include citations where possible.
- Safe fallback is used when evidence is missing, weak, unsafe, or out of scope.
- Low-confidence answer states are captured for analytics and review.
- Prompt-injection risks are explicitly mitigated.
- Logs and metrics capture retrieval quality, latency, token usage, cost, and answer state without exposing secrets or raw prompts.
- Future hybrid search and reranking can be added without weakening tenant isolation.
- Edge cases have tests or documented handling in implementation tasks.
- No code, migrations, dependencies, runtime configuration, or integrations are added by this planning task.

## 19. Future implementation tasks

Recommended future implementation sequence:

1. Define retrieval service input/output schemas with trusted tenant context.
2. Implement tenant and workspace resolution for dashboard and public widget channels.
3. Implement query embedding generation abstraction.
4. Implement pgvector retrieval with mandatory tenant/lifecycle filters.
5. Implement context assembly with source labels and token budgeting.
6. Define runtime prompt template with fallback and prompt-injection protections.
7. Implement citation selection and citation persistence.
8. Implement answer-state classification for answered, low-confidence, fallback, and escalated states.
9. Add logging, metrics, token usage, latency, and cost tracking.
10. Add tenant-isolation tests for retrieval and citations.
11. Add tests for archived, expired, deleted, failed, superseded, and private content exclusion.
12. Add fallback and low-confidence evaluation cases.
13. Add unanswered-question analytics from fallback and low-confidence outcomes.
14. Evaluate hybrid search after MVP vector retrieval is stable.
15. Evaluate reranking only after retrieval baseline metrics exist.

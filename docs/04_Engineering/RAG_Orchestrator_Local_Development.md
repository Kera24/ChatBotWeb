# RAG Orchestrator Local Development

Version: 0.1
Status: Implemented Foundation

## Overview

The internal RAG orchestrator coordinates the first end-to-end grounded-answer flow for dashboard testing. It is implemented in `apps/api/app/ai/rag_orchestrator.py` and exposed through an internal workspace endpoint. The public website widget is still out of scope.

## Flow

1. Validate `organisation_id` and `workspace_id`.
2. Create a new `chat_sessions` row or load the supplied conversation using full tenant scope.
3. Persist the user message.
4. Retrieve tenant-scoped ready chunks through the existing retrieval context service.
5. Build context text and citation candidates.
6. Execute AI Core with the active `grounded_rag_answer` prompt and configured mock model.
7. Persist the assistant message with execution, prompt, model, token, cost, latency, and finish metadata.
8. Persist citations linked to the assistant message.
9. Return a provider-neutral result with conversation/message IDs.

## Internal Endpoint

`POST /api/v1/workspaces/{workspace_id}/rag/answer?organisation_id={organisation_id}`

The endpoint uses the current development RBAC dependency. `org_owner`, `client_admin`, and `viewer` members may call it. Non-members are denied. This remains an authenticated dashboard-test endpoint, not a public widget endpoint.

## Sample Request

```json
{
  "query": "When do applications close?",
  "conversation_id": null,
  "model_key": "mock-grounded-answer",
  "retrieval_limit": 5,
  "max_context_chars": 12000
}
```

## Sample Response

```json
{
  "data": {
    "conversation_id": "...",
    "user_message_id": "...",
    "assistant_message_id": "...",
    "answer": "[mock:...] Deterministic mock response...",
    "answer_state": "answered",
    "citations": [
      {
        "citation_index": 1,
        "chunk_id": "...",
        "document_id": "...",
        "document_version_id": "...",
        "source_title": "Admissions Handbook",
        "source_type": "txt",
        "page_number": 1,
        "section_title": "Admissions",
        "similarity_score": 0.98,
        "quoted_text": "applications close in december"
      }
    ],
    "retrieved_chunk_count": 1,
    "provider_key": "mock",
    "model_key": "mock-grounded-answer",
    "prompt_key": "grounded_rag_answer",
    "fallback_used": false
  }
}
```

## Persistence Behaviour

The user message is stored before retrieval/provider execution. Assistant messages are stored once per orchestrator call. Successful assistant messages include AI execution metadata and citations. Empty retrieval stores a fallback assistant message and zero citations.

## Fallback Behaviour

If no usable context is retrieved, the orchestrator does not call the provider and does not invent an answer. It stores the deterministic fallback response, marks `answer_state` as `fallback`, sets `fallback_used` to true, and stores zero citations.

## Failure Behaviour

If AI Core/provider execution fails after the user message is stored, the orchestrator persists a failed assistant message with `answer_state` set to `failed`, preserves the execution ID and accounting metadata where available, stores no citations, and raises a structured internal API error without stack traces.

## Citation Handling

For this MVP mock-provider slice, persisted citations map directly from authorised retrieval context candidates. Citation records preserve index, chunk, document, document version, source title/type, page, section, similarity score, and safe quoted text. Later citation validation can reduce this candidate set before persistence.

## Mock Provider Warning

The orchestrator still uses the deterministic mock AI provider. No external LLM network call is made, and no OpenAI-compatible provider is implemented in this task.

## Future Idempotency

The current implementation uses one DB session where practical and avoids duplicate assistant messages within a single service call. It does not claim distributed transaction or retry idempotency support. A future endpoint should accept an idempotency key and persist request-level execution state.

# Conversation History API

Version: 0.1
Status: Implemented

## Purpose

The conversation history API exposes read-only dashboard access to tenant-scoped conversations, ordered messages, and citations created by the internal RAG endpoint. It is not a public widget API and does not implement frontend integration.

## RBAC

The endpoints use the current development authentication headers. Access is allowed for organisation members with `org_owner`, `client_admin`, or `viewer`. Non-members and unsupported roles are denied. `super_admin` continues to bypass organisation membership through the existing development dependency.

## Endpoints

### List conversations

`GET /api/v1/workspaces/{workspace_id}/conversations?organisation_id={organisation_id}`

Optional query parameters:

- `status`
- `channel`
- `limit`, default `50`, maximum `100`
- `offset`, default `0`
- `started_after`
- `started_before`

Results are ordered by `last_message_at` descending, then `created_at` descending. Every query is filtered by `organisation_id` and `workspace_id`.

### Conversation detail

`GET /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}?organisation_id={organisation_id}`

Returns conversation metadata, ordered messages, and citations attached to assistant messages.

A separate message-list endpoint is intentionally not implemented for MVP because this detail endpoint returns the complete ordered message list with citations. Add a paginated message endpoint later if conversations become large.

## List Response Example

```json
{
  "data": [
    {
      "id": "...",
      "organisation_id": "...",
      "workspace_id": "...",
      "channel": "dashboard_test",
      "status": "active",
      "title": "Admissions chat",
      "started_at": "2026-07-12T00:00:00Z",
      "last_message_at": "2026-07-12T00:00:03Z",
      "ended_at": null,
      "message_count": 2,
      "last_message_preview": "Applications close in December.",
      "metadata": {"source": "dashboard_test"}
    }
  ],
  "meta": {"limit": 50, "offset": 0}
}
```

## Detail Response Example

```json
{
  "data": {
    "id": "...",
    "channel": "dashboard_test",
    "status": "active",
    "messages": [
      {
        "id": "...",
        "role": "assistant",
        "content": "Applications close in December.",
        "sequence_number": 2,
        "answer_state": "answered",
        "model_key": "mock-grounded-answer",
        "provider_key": "mock",
        "prompt_key": "grounded_rag_answer",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "estimated_cost": "0E-8",
        "latency_ms": 12,
        "finish_reason": "stop",
        "citations": [
          {
            "citation_index": 1,
            "chunk_id": "...",
            "document_id": "...",
            "document_version_id": "...",
            "source_title": "Admissions Handbook",
            "source_type": "txt",
            "quoted_text": "Applications close in December."
          }
        ]
      }
    ]
  }
}
```

## Privacy Rules

Responses preserve user and assistant message content for dashboard review, but intentionally exclude:

- anonymous and external user identifiers
- raw system prompts and rendered prompts
- message `metadata_json`
- provider raw metadata and internal provider payloads
- audit-only metadata
- secrets, stack traces, or hidden implementation details

Cross-tenant detail requests return the same safe not-found response as genuinely missing conversations within the requested tenant scope.

## Retention Placeholder

Conversation retention, redaction, deletion, legal hold, and export workflows are not implemented. A future retention design should define tenant-level retention periods, redaction audit trails, and controls for public user identifiers before exposing public widget history.

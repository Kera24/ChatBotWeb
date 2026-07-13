# Unanswered Review Workflow

Version: 0.1
Status: Implemented

## Purpose

The unanswered review workflow helps client admins find answers that need human attention because the assistant fell back, failed, or returned a low-confidence answer. It does not generate new documents, call an LLM for remediation, aggregate analytics, or expose public-widget behaviour.

## Review Item Derivation

Review items are derived from existing `chat_messages` records where:

- `role = assistant`
- `answer_state` is `fallback`, `failed`, or `low_confidence`

The user question is resolved as the immediately preceding user message in the same tenant-scoped conversation. Citations are read from the existing `citations` table.

## Review Status Model

Mutable review decisions are stored in `review_annotations` rather than on `chat_messages`. This keeps original conversation messages immutable while allowing reviewers to mark operational state.

Statuses:

- `open`
- `reviewed`
- `dismissed`
- `knowledge_gap`

The annotation also stores an optional reviewer note, `reviewed_at`, and `reviewed_by`. Missing annotations are treated as `open`.

## API Endpoints

List review items:

```text
GET /api/v1/workspaces/{workspace_id}/review/unanswered?organisation_id=...
```

Filters:

- `answer_state`
- `review_status`
- `channel`
- `created_after`
- `created_before`
- `limit` with maximum `100`
- `offset`

Detail:

```text
GET /api/v1/workspaces/{workspace_id}/review/unanswered/{assistant_message_id}?organisation_id=...
```

Update review status:

```text
PATCH /api/v1/workspaces/{workspace_id}/review/unanswered/{assistant_message_id}?organisation_id=...
```

Request:

```json
{
  "review_status": "knowledge_gap",
  "reviewer_note": "Add a clearer refund policy article."
}
```

## RBAC

Read access:

- `org_owner`
- `client_admin`
- `viewer`

Update access:

- `org_owner`
- `client_admin`

Development `super_admin` continues to bypass organisation membership checks. Non-members are denied. Cross-tenant or missing review items return safe not-found behaviour.

## Audit Events

Successful review status changes create tenant-scoped audit events:

- `action`: `review.status.changed`
- `entity_type`: `chat_message`
- `entity_id`: assistant message ID
- `previous_status` and `new_status`
- metadata containing conversation ID and answer state

Original user and assistant message content is not mutated.

## Dashboard Routes

- `/review/unanswered` lists flagged answers.
- `/review/unanswered/[messageId]` shows one flagged answer, conversation context, citations, safe technical metadata, and reviewer controls.

The sidebar labels this workflow as `Knowledge Gaps`, which is clearer for non-technical client admins than ?unanswered review queue?.

## Privacy Exclusions

Responses and UI intentionally exclude raw prompts, rendered prompts, message metadata JSON, secrets, provider stack traces, and hidden provider internals. The workflow preserves visible user questions and assistant answers because review requires that conversation content.

## Expressionism Design Application

The queue uses strong state labels and left-edge colour accents to distinguish fallback, failed, and low-confidence answers. Copy is human-centred and operational: it frames the issue as missing or poor knowledge, not a catastrophic system failure. All statuses have text labels and remain keyboard-accessible.

## Future Ideas Out Of Scope

- Suggested FAQ or document drafts.
- AI-generated remediation.
- Knowledge-gap analytics charts.
- Notifications or ticketing integrations.
- Bulk review workflows.
- Public end-user feedback capture.

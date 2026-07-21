# Task: Prompt Assembly Foundation

## Task ID

TASK-038

## Linked epic/story

- EPIC-003

## Objective

Add source-grounded prompt assembly using tenant-scoped retrieval context.

This task creates versioned system and user prompts only. It does not invoke an LLM, generate final answers, create chat sessions, expose widget behaviour, add analytics, or introduce background queues.

## Scope

Implement only:

- Prompt assembly service using retrieval context.
- Source-grounded answer prompt template.
- Prompt version constant and configuration.
- System instructions.
- User question inclusion.
- Retrieved context block inclusion.
- Citation rules.
- Safe fallback rules.
- No-guessing rule.
- Manual/internal prompt endpoint.
- Existing development RBAC placeholder checks.
- Tenant-safe organisation and workspace access.
- Tests for context, citation rules, fallback rules, isolation, authorization, and empty context.
- Sprint pointer update to TASK-038.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/retrieval/prompt?organisation_id=...`

Request body:

```json
{
  "query": "When do applications close?",
  "limit": 5,
  "max_context_chars": 12000
}
```

## Out of scope

Do not implement:

- LLM invocation.
- Final answer generation.
- Chat sessions.
- Widget behaviour.
- Analytics.
- Background queue.

## Requirements

- Prompts use only tenant-scoped retrieval context.
- System prompt explicitly requires source grounding, citations, safe fallback, and no guessing.
- User prompt includes the question and numbered context blocks.
- Empty context still produces a fallback-ready prompt.
- Response preserves context blocks and citation metadata.
- Viewer access follows the current read RBAC decision.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-038-prompt-assembly-foundation.md` exists.
- Prompt assembly service and endpoint exist.
- Prompt version is exposed.
- Tests cover all required behaviours.
- `.ai/CURRENT_SPRINT.md` lists TASK-038 as current task.
- Required validation commands have been run and reported.

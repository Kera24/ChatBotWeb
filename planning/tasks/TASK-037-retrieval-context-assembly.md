# Task: Retrieval Context Assembly

## Task ID

TASK-037

## Linked epic/story

- EPIC-003

## Objective

Add tenant-scoped retrieval context assembly using existing vector search results.

This task converts matching chunks into bounded citation-ready context blocks. It does not implement LLM answer generation, prompt templates, a final RAG endpoint, widget, analytics, or background queue behaviour.

## Scope

Implement only:

- Retrieval context assembly service.
- Existing vector search integration.
- Citation-ready context block creation.
- Maximum context chunk enforcement.
- Maximum context character enforcement.
- Source metadata preservation.
- Manual/internal retrieval context endpoint.
- Existing development RBAC placeholder checks.
- Tenant-safe organisation and workspace access.
- Tests for context assembly, limits, citations, isolation, authorization, and empty results.
- Sprint pointer update to TASK-037.

## Endpoint

- `POST /api/v1/workspaces/{workspace_id}/retrieval/context?organisation_id=...`

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

- LLM answer generation.
- Prompt templates.
- Final RAG answer endpoint.
- Widget behaviour.
- Analytics.
- Background queue.

## Requirements

- Context is assembled only from tenant-scoped vector search matches.
- Maximum context chunks and characters are enforced.
- Context blocks preserve document, version, chunk, title, type, page, section, and score metadata.
- Citations are returned separately from context text.
- Empty search results return empty context blocks and citations.
- Viewer access follows the current read RBAC decision.

## Validation commands

Run:

```bash
npm run api:test
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-037-retrieval-context-assembly.md` exists.
- Context assembly service and endpoint exist.
- Limits and citation metadata are implemented.
- Tests cover all required behaviours.
- `.ai/CURRENT_SPRINT.md` lists TASK-037 as current task.
- Required validation commands have been run and reported.

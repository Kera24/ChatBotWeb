# Task: Frontend API Integration Planning

## Task ID

TASK-009

## Linked epic/story

- EPIC-002

## Objective

Plan how the Next.js dashboard will integrate with the FastAPI tenant APIs without implementing live frontend API calls yet.

This is a planning task only. Do not wire real frontend data fetching in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `docs/02_Architecture/03_API_Specification.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `planning/tasks/TASK-008-auth-rbac-implementation.md`
- `apps/web/README.md`

## Frontend API client structure

Future implementation should centralise dashboard API calls under `apps/web/lib/api/`.

Recommended structure:

```text
apps/web/lib/api/
  client.ts              # fetch wrapper, base URL, auth/session headers
  errors.ts              # typed API error handling
  types.ts               # shared response envelope types
  organisations.ts       # admin organisation calls
  workspaces.ts          # workspace calls
  widget-public.ts       # public widget API client, separate from dashboard client
```

Rules:

- Do not call `fetch` directly from every page.
- Keep dashboard API client separate from public widget API client.
- Model the backend response envelope:

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

- Treat failed `success: false`, `401`, `403`, `404`, `409`, and `422` responses as typed UI states.

## Auth token/session strategy placeholder

TASK-008 uses development-only headers:

- `X-Development-User-Email`
- `X-Development-Role`

Future frontend implementation may use those headers only behind an explicit local-development flag.

Production direction:

- Dashboard auth should use the selected hosted auth provider session.
- The frontend should obtain a dashboard session/token from the provider.
- The API client should attach the session/token to protected dashboard requests.
- Provider-specific logic should stay in a small auth adapter, not spread across pages.

Do not store long-lived secrets in the browser.

## Tenant/workspace context strategy

The dashboard must maintain explicit tenant context:

- current organisation
- current workspace
- current user role/membership

Initial frontend state plan:

- Resolve available organisations from protected admin/org endpoints after auth exists.
- Resolve workspace list from `/api/v1/orgs/{organisation_id}/workspaces`.
- Store selected organisation/workspace in route state or a controlled client-side context.
- Do not infer tenant context from `workspace_id` alone.

Important temporary API rule:

- `GET /api/v1/workspaces/{workspace_id}` currently requires `organisation_id` as a query parameter because production auth cannot yet infer tenant context.
- The frontend must pass both `organisation_id` and `workspace_id` until the backend has a safe authenticated tenant-context resolver.

## Error handling pattern

Frontend API errors should map to predictable UI states:

- `401`: session missing or expired; show sign-in/session recovery state once auth exists.
- `403`: user lacks membership or role; show access-denied state.
- `404`: organisation/workspace/resource not found in current tenant context.
- `409`: duplicate slug or conflicting state.
- `422`: validation error; show field-level or request-level validation feedback.
- network failure: show retryable connection state.

Errors must not expose stack traces, internal IDs beyond required resource IDs, secrets, or provider internals.

## Loading, empty, and error UI states

Every dashboard page that fetches data later must define:

- loading state
- empty state
- error state
- access denied state where permissions apply
- stale/retry state where network requests can fail

Expressionism remains the design principle, but trust-critical states must be clear and professional.

Do not hide:

- tenant context
- permission failures
- source-grounding status
- unsafe or missing data states

## Dashboard data fetching plan

Recommended order for future implementation:

1. Add frontend environment variable for API base URL.
2. Add typed API client and response envelope handling.
3. Add auth/session adapter placeholder.
4. Add organisation list fetch for super-admin contexts.
5. Add workspace list fetch for selected organisation.
6. Add workspace detail fetch using `organisation_id + workspace_id`.
7. Replace placeholder page content one page at a time.

Do not fetch RAG, documents, widget, analytics, billing, or user invitation data until those backend tasks exist.

## Public widget API separation

The public widget API must remain separate from dashboard APIs.

Future public widget client rules:

- Uses public workspace key, not dashboard user auth.
- Validates active organisation/workspace on the backend.
- Must support allowed domain checks and rate limiting when implemented.
- Must not attach dashboard session tokens.
- Must not call admin, org, or workspace dashboard endpoints.

## Tests required later

Future frontend implementation must include tests for:

- API client attaches dashboard auth/session headers correctly.
- API client does not attach dashboard auth headers to public widget calls.
- `organisation_id` is included for workspace detail requests.
- `401` maps to session/auth UI state.
- `403` maps to access-denied UI state.
- `404` maps to tenant-scoped not-found state.
- Loading and empty states render for organisation and workspace pages.
- Duplicate slug `409` shows a clear conflict message.
- Workspace selector never shows workspaces from another organisation.

## Acceptance criteria for future implementation

- [ ] API client lives in a central `apps/web/lib/api/` module.
- [ ] Dashboard and public widget clients are separate.
- [ ] Auth/session handling is adapter-based and does not leak provider details across pages.
- [ ] Tenant context includes both organisation and workspace.
- [ ] Workspace detail requests use `organisation_id + workspace_id`.
- [ ] Pages have loading, empty, error, and access-denied states.
- [ ] Tests cover auth headers, tenant context, and error mapping.
- [ ] No live API calls are added before the approved implementation task.

## Out of scope for this planning task

- Live frontend API calls.
- Login UI.
- Auth provider integration.
- RAG.
- Document upload.
- Widget runtime.
- Billing.
- Analytics.

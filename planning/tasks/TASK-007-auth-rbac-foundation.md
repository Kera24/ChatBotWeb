# Task: Auth and RBAC Foundation Planning

## Task ID

TASK-007

## Linked epic/story

- EPIC-002

## Objective

Define the future authentication and RBAC implementation plan before adding production auth code.

This is a planning task only. Do not implement authentication in this task.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `docs/02_Architecture/03_API_Specification.md`
- `planning/epics/EPIC-002-tenant-management.md`
- `planning/tasks/TASK-005-database-tenancy-foundation.md`
- `planning/tasks/TASK-006-tenant-api-foundation.md`

## Auth provider options

Evaluate these options before implementation:

### Supabase Auth

Pros:

- Fast MVP path.
- Hosted user management.
- Email/password and magic link support.
- Can integrate with PostgreSQL-backed product data.

Cons:

- Provider-specific JWT and user model assumptions.
- Requires clear separation between auth identity and platform membership.

### Auth0

Pros:

- Mature enterprise auth provider.
- Good future SSO support.
- Strong tenant/customer identity features.

Cons:

- More setup and cost for MVP.
- Can be heavier than needed for early pilot.

### Clerk

Pros:

- Strong developer experience.
- Good Next.js integration.
- Hosted user/session management.

Cons:

- Backend FastAPI integration and membership mapping still need careful design.
- Vendor-specific user/session concepts.

### Custom auth

Pros:

- Full control.

Cons:

- Not recommended for MVP.
- Higher security and maintenance burden.

## Recommended MVP auth approach

Use a hosted auth provider for dashboard authentication.

Recommended MVP default: Supabase Auth, unless a later architecture decision selects another provider.

Implementation should keep auth provider details behind backend dependencies so the provider can change later.

The platform database remains the source of truth for:

- `users`
- `organisations`
- `workspaces`
- `memberships`
- platform roles

The external auth provider is the source of truth for identity/session verification only.

## RBAC enforcement model

All protected dashboard routes must resolve:

1. Authenticated user identity.
2. Local `users` record mapped from auth provider identity.
3. Organisation membership.
4. Role permission.
5. Workspace access where applicable.

Route dependencies should be explicit:

- `require_authenticated_user`
- `require_super_admin`
- `require_organisation_role`
- `require_workspace_access`

Repository functions must continue to require tenant context and must not rely on auth checks alone.

## Dashboard auth requirements

- Dashboard APIs require authenticated sessions or bearer tokens.
- Admin organisation routes require `super_admin`.
- Organisation workspace routes require `org_owner` or `client_admin`.
- Future knowledge management routes require role-specific checks.
- Failed auth returns `401`.
- Failed permission returns `403`.
- Missing tenant context fails safely.

## Public widget auth model

Public widget endpoints do not use dashboard user auth.

They must use:

- Public workspace key.
- Active organisation status.
- Active workspace status.
- Allowed domain checks.
- Rate limits.
- Abuse detection later.

The public key is not a secret. It identifies a workspace and must never bypass tenant filters.

## Temporary dev-mode limitations

Current TASK-006 APIs use a development-only actor dependency.

Limitations:

- It is not authentication.
- It does not verify identity.
- It does not enforce membership.
- It must not be used in production.
- It must be removed or replaced when TASK-007 implementation begins.

Future auth implementation must fail closed if development mode is disabled and no authenticated user is present.

## Tenant membership checks

Membership checks must verify:

- User exists.
- Organisation exists and is active.
- Membership exists for `organisation_id` and `user_id`.
- Membership status is active.
- Role is allowed for the requested capability.
- Workspace belongs to the organisation when workspace access is required.

Do not fetch tenant-scoped resources by ID alone.

Workspace-scoped access must include:

- `organisation_id`
- `workspace_id`
- authenticated user membership or valid public widget context

## Tests required for auth implementation

Future implementation must include tests for:

- Unauthenticated dashboard request returns `401`.
- Authenticated user without membership returns `403`.
- User cannot access another organisation's workspaces.
- User cannot fetch workspace detail with the wrong organisation context.
- `super_admin` can list/create organisations.
- Non-super-admin cannot list/create organisations.
- `org_owner` and `client_admin` can list/create workspaces in their organisation.
- `viewer` cannot create workspaces.
- Inactive memberships are rejected.
- Inactive organisations and workspaces are rejected.
- Public widget key cannot access dashboard APIs.
- Public widget requests require active organisation/workspace and allowed domain.

## Acceptance criteria for future implementation

- [ ] Auth provider selected and documented.
- [ ] Auth provider identity maps to local `users`.
- [ ] Development-only auth placeholder is removed or gated safely.
- [ ] Protected dashboard routes require authenticated identity.
- [ ] Admin routes enforce `super_admin`.
- [ ] Organisation routes enforce active membership and allowed roles.
- [ ] Workspace routes enforce organisation and workspace context.
- [ ] Public widget auth model is separate from dashboard auth.
- [ ] Tests prove cross-tenant access is rejected.
- [ ] Tests prove role restrictions are enforced.
- [ ] No secrets are committed.
- [ ] Documentation is updated with setup and environment variables.

## Out of scope for this planning task

- Auth implementation.
- Login UI.
- User invitation flow.
- Password reset.
- SSO.
- Billing.
- RAG.
- Document upload.
- Widget runtime.
- Analytics.

# Web App

Client-facing dashboard and future marketing site.

## Responsibilities

- Client admin dashboard
- Knowledge base management UI
- Chatbot configuration UI
- Analytics UI
- User and role management UI

## Planned stack

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

## Initial routes

- `/` dashboard overview
- `/knowledge` knowledge base
- `/chatbot` chatbot configuration
- `/analytics` analytics
- `/users` users and roles
- `/settings` workspace settings


## Conversation history integration

The dashboard includes temporary development-only conversation history routes:

- `/conversations`
- `/conversations/[conversationId]`

Required local environment values:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DEVELOPMENT_ORGANISATION_ID=replace-with-local-organisation-id
NEXT_PUBLIC_DEVELOPMENT_WORKSPACE_ID=replace-with-local-workspace-id
NEXT_PUBLIC_DEVELOPMENT_USER_EMAIL=dev-super-admin@example.test
NEXT_PUBLIC_DEVELOPMENT_ROLE=super_admin
```

These values are temporary and must not be treated as production authentication. Dashboard API calls centralise development headers in `lib/auth/development-session.ts`; future public-widget clients must stay separate.

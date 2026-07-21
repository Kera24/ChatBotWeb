# Web App

Client-facing dashboard and future marketing site.

## Responsibilities

- Client admin dashboard
- Knowledge base management UI
- Chatbot configuration UI
- Analytics UI
- User and role management UI

## Stack

- Next.js
- TypeScript
- Vitest
- React Testing Library
- Testing Library user-event
- jsdom

Tailwind CSS and shadcn/ui remain possible future additions, but the current dashboard uses plain CSS modules/global styles and focused React components.

## Initial routes

- `/` dashboard overview
- `/knowledge` knowledge base
- `/chatbot` chatbot configuration
- `/analytics` analytics
- `/review/unanswered` knowledge gap review queue
- `/review/unanswered/[messageId]` review item detail
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

## Frontend testing

Run the dashboard tests from the repository root:

```bash
npm run web:test
```

Or from `apps/web`:

```bash
npm run test
npm run test:run
```

Tests use Vitest, React Testing Library, user-event, and jsdom. API tests mock `fetch`; they do not call a live backend and do not add public-widget behaviour.

## Knowledge gap review

The dashboard includes temporary development-only review routes for fallback, failed, and low-confidence answers:

- `/review/unanswered`
- `/review/unanswered/[messageId]`

The workflow uses the same central dashboard API client and development tenant configuration as conversation history. Viewers may read review items; `org_owner` and `client_admin` users may update review status.

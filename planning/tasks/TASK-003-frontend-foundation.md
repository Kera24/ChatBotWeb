# Task: Frontend Foundation

## Task ID

TASK-003

## Linked epic/story

- EPIC-001

## Objective

Create a minimal Next.js frontend foundation for the client dashboard with an expressive, professional, accessible dashboard shell and placeholder pages.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/context/design-principles.md`
- `.ai/CURRENT_SPRINT.md`
- `apps/web/README.md`
- `docs/05_Design/01_Design_System.md`
- `planning/epics/EPIC-001-platform-foundation.md`

## Files to create or modify

- `apps/web/app/layout.tsx`
- `apps/web/app/page.tsx`
- `apps/web/app/globals.css`
- `apps/web/app/knowledge/page.tsx`
- `apps/web/app/chatbot/page.tsx`
- `apps/web/app/analytics/page.tsx`
- `apps/web/app/users/page.tsx`
- `apps/web/app/settings/page.tsx`
- `apps/web/components/dashboard-shell.tsx`
- `apps/web/components/placeholder-page.tsx`
- `apps/web/lib/navigation.ts`
- `apps/web/next.config.mjs`
- `apps/web/tsconfig.json`
- `apps/web/package.json` if scripts need adjustment

## Technical requirements

1. Use Next.js with TypeScript.
2. Create a dashboard shell with sidebar navigation.
3. Add placeholder pages for:
   - Overview
   - Knowledge Base
   - Chatbot
   - Analytics
   - Users
   - Settings
4. Use Expressionism as the major visual design principle while preserving professional trust and accessibility.
5. Keep UI static and local-only.
6. Do not connect to the backend.
7. Do not implement authentication.
8. Do not implement real data fetching.
9. Do not add product feature behavior beyond placeholders.

## Constraints

- No backend integration yet.
- No auth implementation yet.
- No real tenant data yet.
- No RAG, ingestion, widget runtime, analytics runtime, or user-management behavior.
- No secrets.

## Acceptance criteria

- [ ] Next.js app imports and builds cleanly.
- [ ] Dashboard shell exists.
- [ ] Sidebar navigation links to all required placeholder pages.
- [ ] Placeholder pages render without backend calls.
- [ ] Visual direction follows Expressionism while remaining accessible and professional.
- [ ] No feature scope creep.

## Required checks

- Run frontend build if dependencies are available.
- Run frontend lint if configured and available.

## Manual verification

Run the web app locally and visit:

- `/`
- `/knowledge`
- `/chatbot`
- `/analytics`
- `/users`
- `/settings`

## Definition of done

- [ ] Frontend foundation implemented
- [ ] Placeholder pages added
- [ ] Build/lint attempted
- [ ] No backend, auth, or data-fetching implementation added
- [ ] Ready for future frontend feature tasks

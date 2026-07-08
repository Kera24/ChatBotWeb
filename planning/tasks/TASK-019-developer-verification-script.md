# Task: Developer Verification Script

## Task ID

TASK-019

## Linked epic/story

- EPIC-001

## Objective

Add a single root-level developer verification command that checks the local Compose configuration, API tests, web linting, and web production build.

This task improves local development confidence only. It does not add product behavior.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `docs/04_Engineering/Local_Development.md`
- `planning/tasks/TASK-018-root-test-and-api-db-hardening.md`

## Scope

Implement only:

- A root-level developer verification npm command or script.
- Verification steps for `docker compose config`, `npm run api:test`, `npm run web:lint`, and `npm run web:build`.
- Documentation for the verification command.
- Optional documentation for Alembic verification as a separate PostgreSQL-dependent step.
- Sprint pointer update to TASK-019.

## Out of scope

Do not implement:

- Workers.
- Document upload.
- RAG runtime.
- Widget behavior.
- Analytics behavior.

## Requirements

- The verification command runs from the repository root.
- The command remains compatible with Windows developer environments.
- The command uses existing app-specific npm scripts rather than duplicating their internals.
- Alembic/PostgreSQL verification remains documented separately because it requires a running database and `DATABASE_URL`.

## Validation commands

Run:

```bash
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-019-developer-verification-script.md` exists.
- `package.json` exposes a root-level verification command.
- Local development docs list the verification command and what it runs.
- `.ai/CURRENT_SPRINT.md` lists TASK-019 as current task.
- The new verification command has been run and reported.

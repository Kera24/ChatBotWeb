# Task: CI Verify Workflow

## Task ID

TASK-020

## Linked epic/story

- EPIC-001

## Objective

Add a lightweight GitHub Actions workflow that runs the repository verification command on pull requests and pushes to `main`.

This task adds CI coverage only. It does not add product behavior.

## Scope

Implement only:

- GitHub Actions workflow for pull requests.
- GitHub Actions workflow for pushes to `main`.
- Node setup for web dependency installation and build commands.
- Python setup for API dependency installation and test commands.
- Dependency installation for API and web apps.
- `npm run verify` execution.

## Out of scope

Do not implement:

- Workers.
- Document upload.
- RAG runtime.
- Widget behavior.
- Analytics behavior.
- Required Docker service containers beyond `docker compose config`.

## Requirements

- Workflow runs on pull requests.
- Workflow runs on pushes to `main`.
- Workflow uses appropriate Node and Python setup actions.
- Workflow installs API dependencies before API tests.
- Workflow installs web dependencies before lint/build.
- Workflow stays lightweight and only validates Docker Compose syntax through `npm run verify`.

## Validation commands

Run locally:

```bash
npm run verify
```

## Acceptance criteria

- `planning/tasks/TASK-020-ci-verify-workflow.md` exists.
- `.github/workflows/verify.yml` exists.
- Workflow runs `npm run verify`.
- `.ai/CURRENT_SPRINT.md` lists TASK-020 as current task.
- Local `npm run verify` has been run and reported.

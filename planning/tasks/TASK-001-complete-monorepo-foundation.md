# Task: Complete Monorepo Foundation

## Task ID

TASK-001

## Linked epic/story

- EPIC-001

## Objective

Complete the lightweight monorepo foundation so the repository has clear app, service, package, infrastructure, documentation, and planning boundaries.

## Context for coding agent

Read these files first:

- README.md
- docs/07_Roadmap/01_MVP_Implementation_Plan.md
- docs/02_Architecture/01_System_Architecture.md
- planning/epics/EPIC-001-platform-foundation.md

## Files to create or modify

- package.json
- apps/web/*
- apps/admin/*
- apps/widget/*
- apps/api/*
- services/*
- packages/*
- infrastructure/*
- scripts/*

## Technical requirements

1. Keep the foundation lightweight.
2. Avoid building product features in this task.
3. Create enough structure for future implementation tasks.
4. Add README files to major folders.
5. Ensure naming is consistent.

## Constraints

- Do not implement authentication.
- Do not implement database migrations.
- Do not implement RAG yet.
- Do not introduce unnecessary dependencies.

## Acceptance criteria

- [ ] Root workspace manifest exists.
- [ ] Apps folders exist and document responsibilities.
- [ ] Services folders exist and document responsibilities.
- [ ] Packages folders exist and document responsibilities.
- [ ] Infrastructure folder exists and documents future deployment direction.
- [ ] API app has a health endpoint.
- [ ] Web app has a minimal package manifest.

## Required tests

- API health endpoint test should be added in a later backend task.

## Manual verification

1. Review folder structure.
2. Confirm README files explain purpose.
3. Confirm no feature work was added prematurely.

## Definition of done

- [ ] Structure complete
- [ ] Documentation added
- [ ] No secrets committed
- [ ] Ready for backend foundation task

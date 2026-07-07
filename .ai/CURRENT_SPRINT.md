# Current Sprint

Current focus: Sprint 0 Foundation.

Source sprint plan:

- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `docs/07_Roadmap/01_MVP_Implementation_Plan.md`
- `planning/tasks/TASK-001-complete-monorepo-foundation.md`
- `planning/tasks/TASK-002-backend-foundation.md`

## Sprint goal

Create a clean repository, backend foundation, frontend foundation, local development structure, and quality baseline.

## Active priorities

1. Complete monorepo foundation.
2. Keep backend foundation minimal and testable.
3. Keep frontend foundation as structure only until an approved UI task exists.
4. Keep local development instructions clear.
5. Establish tenant-isolation patterns before implementing tenant data access.

## Guardrails

- Do not implement production product features without a task.
- Do not build the actual expressive UI yet.
- Do not add authentication, billing, ingestion, embeddings, chat runtime, or widget behavior unless the active task calls for it.
- Do not add dependencies unless required by the active foundation task.
- Do not store secrets in code, docs, tests, examples, or environment files.

## Definition of done for Sprint 0

- Backend health endpoint works.
- Frontend app can run.
- Repository has clear workspace structure.
- Basic local development instructions exist.
- Agents can understand where to find product, architecture, security, RAG, design, and planning context.

## Next sprint preview

Sprint 1 is Database and Tenancy. It must establish organisation, workspace, user, membership, migration, and tenant-isolation test patterns before higher-level features are built.

## Current/Next Planning Task

- `planning/tasks/TASK-009-frontend-api-integration-planning.md`

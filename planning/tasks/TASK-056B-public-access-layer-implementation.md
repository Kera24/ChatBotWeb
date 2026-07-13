# TASK-056B - Public Access Layer Implementation

## Task ID

TASK-056B

## Linked epic/story

- EPIC-004
- TASK-056A

## Type

Implementation task. Do not start until TASK-056A is approved.

## Objective

Implement the minimal internal Public Access Layer service skeleton and contracts without exposing public endpoints or enabling public traffic.

## Context for coding agent

Read:

- Approved `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- Existing RAG Orchestrator implementation and tests

## Files to create or modify

To be finalised after TASK-056A approval. Expected future areas may include:

- `apps/api/app/public_access/`
- Unit tests for pure service contracts
- Documentation updates

## Technical requirements

- Define typed request/result/error contracts.
- Define channel adapter interface.
- Define tenant-resolution interface without implementing public key schema.
- Define policy-check interfaces for validation, rate limits, and cost limits.
- Add tests for contract behaviour using in-memory stubs.
- Ensure no public routes are added.

## Constraints

- Do not add public endpoints.
- Do not add database migrations.
- Do not add Redis limiter implementation.
- Do not add anonymous sessions.
- Do not call RAG from public traffic.
- Do not implement widget UI.
- Do not bypass approved architecture.

## Acceptance criteria

- [ ] Public Access Layer contracts exist internally.
- [ ] Channel adapter interface exists.
- [ ] Safe error codes are represented.
- [ ] Tests prove no dashboard/development auth headers are accepted by public contracts.
- [ ] Tests prove tenant context must be server-resolved before orchestration.
- [ ] No public endpoint is exposed.

## Required tests

- Unit tests for request validation contracts.
- Unit tests for safe error mapping.
- Unit tests for adapter interface stubs.
- Tests proving unresolved tenant context cannot proceed.

## Manual verification

Run the repository verification command after implementation:

```bash
npm run verify
```

## Definition of done

- [ ] Code complete within approved scope.
- [ ] Tests pass.
- [ ] No tenant isolation regressions.
- [ ] No public endpoints exposed.
- [ ] Documentation updated.
- [ ] Ready for review.

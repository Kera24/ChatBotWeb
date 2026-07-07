# Coding Standards

Primary sources:

- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/04_Backend/01_Backend_Engineering_Standards.md`
- `docs/04_Engineering/01_Development_Roadmap.md`
- `docs/04_Engineering/02_AI_Assisted_Development_Tasks.md`

## General standards

- Keep changes scoped to the active task.
- Prefer existing patterns over new abstractions.
- Add tests proportional to risk.
- Keep behavior and docs aligned.
- Do not add major dependencies without justification and likely an ADR.
- Do not commit generated clutter, secrets, local caches, or environment-specific output.

## Backend standards

- Use FastAPI patterns consistently.
- Keep configuration environment-driven.
- Keep routers modular.
- Validate inputs at API boundaries.
- Return clear errors.
- Use dependency injection for shared request context.
- Enforce tenant context before accessing tenant data.

## Frontend standards

- Use Next.js, TypeScript, Tailwind CSS, and shadcn/ui direction.
- Keep components accessible.
- Keep forms clear, validated, and keyboard-friendly.
- Preserve responsive layout behavior.
- Follow `.ai/context/design-principles.md` for expression and product personality.

## AI/RAG standards

- Source-grounded answers only.
- No guessing when retrieval evidence is insufficient.
- Citations should be explicit when possible.
- Retrieval must be tenant-filtered.
- Prompt changes should be reviewed for injection resistance and data leakage.

## Testing expectations

- Tenant isolation tests are required for tenant-scoped behavior.
- Permission checks require tests.
- Public endpoints require abuse, rate-limit, and input-validation consideration.
- RAG changes require evaluation or clear manual test cases.

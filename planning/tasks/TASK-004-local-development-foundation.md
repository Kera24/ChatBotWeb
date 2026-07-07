# Task: Local Development Foundation

## Task ID

TASK-004

## Linked epic/story

- EPIC-001

## Objective

Create clear local development documentation and safe repository defaults so human developers and AI coding agents can install, run, test, lint, and build the current API and web foundations consistently.

## Context for coding agent

Read these files first:

- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`
- `planning/epics/EPIC-001-platform-foundation.md`
- `docs/07_Roadmap/01_MVP_Implementation_Plan.md`
- `apps/api/README.md`
- `apps/web/README.md`

## Files to create or modify

- `docs/04_Engineering/Local_Development.md`
- `README.md`
- `.gitignore`
- `package.json` if useful for root workspace commands

## Technical requirements

1. Document local setup prerequisites.
2. Document standard commands for:
   - API install
   - API run
   - API tests
   - web install
   - web dev
   - web lint
   - web build
3. Add safe ignore rules for generated files.
4. Add root package scripts only if they make local commands clearer.
5. Keep Docker out of scope unless already clearly planned for this task.

## Constraints

- Do not add database implementation.
- Do not add authentication.
- Do not add RAG.
- Do not add tenancy.
- Do not add backend product features.
- Do not add secrets.

## Acceptance criteria

- [ ] Local development guide exists.
- [ ] README links to the local development guide.
- [ ] Generated files are ignored safely.
- [ ] API and web commands are documented.
- [ ] Root scripts exist if useful and do not add runtime dependencies.
- [ ] Verification commands are run where possible.

## Required checks

- API tests
- Web lint
- Web build

## Definition of done

- [ ] Developers can find setup commands from the root README.
- [ ] Generated local artifacts are not shown as source changes.
- [ ] No product feature scope creep.
- [ ] Ready for the next Sprint 0 or Sprint 1 task.

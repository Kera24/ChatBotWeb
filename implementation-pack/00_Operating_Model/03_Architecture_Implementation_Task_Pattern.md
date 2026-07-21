# Architecture and Implementation Task Pattern

Version: 0.1
Status: Active

## 1. Purpose

Every major feature must be split into two task types:

1. Architecture task.
2. Implementation task.

The architecture task must be reviewed and approved before implementation starts. This keeps Codex sessions, human engineers, and reviewers aligned on boundaries before code is written.

## 2. When This Pattern Applies

Use the architecture-then-implementation pattern for any work that introduces or materially changes:

- Public or external APIs.
- Authentication, authorisation, tenant resolution, or security boundaries.
- Database schema, migrations, retention, or lifecycle state.
- RAG orchestration, retrieval, prompt, model, provider, or AI Core behaviour.
- Cross-channel platform capabilities.
- Background workers or queues.
- Billing, analytics, audit, observability, or cost controls.
- Product workflows with persistent state.
- UI flows that depend on new backend contracts.

Small copy edits, test-only changes, isolated bug fixes, and documentation corrections may remain single tasks when they do not change architecture.

## 3. Architecture Task Requirements

An architecture task must produce planning artifacts only. It must not implement product code.

Required sections:

- Objective.
- Context and source documents read.
- Bounded context and ownership.
- Data model proposal where relevant.
- API contract proposal where relevant.
- Service/repository/module boundaries.
- Security and tenant isolation rules.
- RAG/source-grounding implications where relevant.
- Error model.
- Observability and audit events.
- Test strategy.
- Implementation phases.
- Explicit out-of-scope list.
- Acceptance criteria.

Architecture tasks may create or update:

- `implementation-pack/**` architecture documents.
- `docs/adr/**` records.
- `planning/epics/**`.
- Future implementation task files.
- `.ai` context and sprint files.

Architecture tasks must not create:

- Database migrations.
- Runtime routes or endpoint handlers.
- Production code paths.
- UI routes/components unless the task is explicitly a design artifact and not executable code.
- Dependencies.

## 4. Implementation Task Requirements

An implementation task may begin only after the linked architecture task is approved.

Required sections:

- Link to approved architecture task.
- Link to ADR or architecture document.
- Exact files/modules expected to change.
- Acceptance criteria inherited from architecture.
- Tests to add and commands to run.
- Security and tenant-isolation checks.
- Documentation updates.
- Rollback or migration notes where relevant.

Implementation tasks must not change the approved architecture silently. If implementation discovers an architecture gap, stop and create an architecture amendment or ADR update before continuing.

## 5. Naming Convention

Use paired tasks when practical:

```text
TASK-056A-public-access-layer-architecture.md
TASK-056B-public-access-layer-implementation.md
```

Use the `A` suffix for architecture and `B` for implementation. Larger features may have multiple implementation tasks after one architecture task.

## 6. Approval Gate

Before an implementation task starts, verify:

- Architecture task status is approved or accepted.
- Relevant ADR is accepted when the feature changes a major boundary.
- Out-of-scope list is clear.
- Test strategy is specific.
- Tenant isolation is specified.
- Public/security implications are explicit.

If any item is missing, implementation must not start.

## 7. Codex Session Rule

When a user asks Codex to implement a major feature and no approved architecture task exists, Codex must create or request the architecture task first. Codex must not skip directly to implementation for major bounded-context work.

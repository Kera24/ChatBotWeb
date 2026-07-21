# Task: <Task Name>

## Task ID

TASK-XXX

## Task type

Architecture | Implementation | Documentation | Bugfix

For major features, create an Architecture task first and an Implementation task second. Implementation must not start until the linked Architecture task is approved.

## Linked epic/story

- EPIC-XXX
- STORY-XXX

## Linked architecture

Required for implementation tasks:

- Architecture task: TASK-XXXA
- Architecture document: path/to/architecture.md
- ADR: docs/adr/XXXX-title.md
- Approval status: Draft | Approved

## Objective

Describe the exact architecture or implementation outcome.

## Context for coding agent

Include links to relevant docs, constraints, existing files, and approved architecture.

## Files to create or modify

- path/to/file
- path/to/other-file

## Technical requirements

- Requirement 1
- Requirement 2
- Requirement 3

## Security and tenant isolation

- Tenant context requirements
- Auth/RBAC requirements
- Public/private boundary rules
- Data privacy requirements

## Constraints

- Constraint 1
- Constraint 2

## Out of scope

- Exclusion 1
- Exclusion 2

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Required tests

- Unit tests
- Integration tests
- Security tests where relevant
- Tenant isolation tests where relevant

## Manual verification

Steps a human should run to verify the task.

## Definition of done

- [ ] Architecture approved before implementation, if applicable
- [ ] Code complete, if implementation task
- [ ] Tests pass or not applicable for planning-only tasks
- [ ] No tenant isolation regressions
- [ ] Documentation updated
- [ ] Ready for review

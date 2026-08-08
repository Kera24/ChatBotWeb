# ADR-0030: Developer Operating System (CLAUDE.md, .skills/, .prompts/, docs/architecture/)

Status: Accepted
Date: 2026-08-07

## Context

Repeated implementation tasks (by human contributors and by Claude Code) were re-deriving the same architectural context, coding conventions, validation commands, and file-boundary rules from scratch each time — reading the same source files, re-learning the same RBAC pattern, re-discovering the same "never touch billing without explicit instruction" rules. This cost time and produced inconsistent results across tasks. The team had to decide whether to formalize this repeated context into a reusable, structured set of files, and if so, what shape it should take.

## Decision

Build a permanent "developer operating system": `CLAUDE.md` (primary instruction file), `docs/CONSTITUTION.md` (mission/vision/philosophy), `docs/architecture/*.md` (15 current-state architecture references), `docs/design/design-system.md`, `.prompts/*.md` (10 reusable task-prompt templates), `.skills/*/SKILL.md` (10 reusable skill definitions), plus `docs/file-boundaries.md`, `docs/validation-policy.md`, `docs/reporting-policy.md`, `docs/token-optimisation.md`, `docs/development-playbook.md`.

## Alternatives

- **Keep relying on ad hoc context-gathering per task** — rejected: this was the status quo and the source of the problem (token cost, inconsistency, repeated mistakes on already-known constraints like billing/evaluation-threshold sensitivity).
- **A single giant reference document instead of a structured set** — rejected: a single document doesn't let a task pull in only the relevant slice (e.g. a frontend-only task shouldn't need to load billing/guardrail context); the `.skills/`/`.prompts/` split by domain exists specifically so tasks can stay narrowly scoped, which is also more token-efficient.
- **Generate context freshly per task via broad codebase search instead of maintaining static docs** — rejected: broad search is slower and less reliable than a maintained reference, and doesn't capture *decisions* (why something is built this way), only current state — this is also why `docs/engineering/`, `docs/adr/` (this Engineering Brain effort, `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md`) exists as a complementary, decision-focused layer on top.

## Tradeoffs

- Gains: dramatically reduced token usage and repeated architectural reasoning per task; consistent file-boundary and validation behavior across different tasks and different sessions; a single entry point (`CLAUDE.md`) new contributors (human or AI) can start from.
- Costs: the developer operating system itself requires maintenance — if `docs/architecture/*.md` drifts from actual code, it becomes actively misleading rather than merely absent (a real risk the "Supersedes" notes on pre-existing v0.1 draft docs were written to manage, see `docs/README.md`).

## Consequences

- Future architecture-affecting changes should update the relevant `docs/architecture/*.md` file (and `.skills`/`.prompts` if the change affects how a task should be scoped) as part of the same change, not as separate follow-up work.
- `docs/file-boundaries.md` and `CLAUDE.md`'s "things Claude must never do" list are the authoritative source for what's off-limits without explicit instruction (billing, evaluation thresholds, Azure, CI/CD, database schema) — this Engineering Brain effort's own constraints (no commits, no production changes, documentation only) are an instance of that same pattern, not a special case.

## Future reconsideration triggers

Evidence that the `.skills`/`.prompts` structure itself is being ignored or bypassed in practice, or that `docs/architecture/*.md` has drifted significantly from actual code (which would call for a refreshed audit pass, not a change in approach).

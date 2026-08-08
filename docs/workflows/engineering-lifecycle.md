# Engineering Lifecycle

The complete lifecycle every piece of engineering work at Conversa moves through, from idea to production and back into the next idea. This is the master workflow — `docs/workflows/ai-development.md` and `docs/workflows/feature-development.md` are specializations of it for AI-model work and product features respectively; `docs/checklists/*.md` are the per-stage verification tools; `docs/sops/*.md` and `docs/runbooks/*.md` are what you reach for when a stage fails.

```
Idea → Requirements → Architecture Review → Technical Design → Specification
  → Implementation → Unit Tests → Integration Tests → Evaluation → Guardrails
  → Graders → Performance Validation → Security Validation → Observability
  → Human Review → Release Approval → Deployment → Production Monitoring
  → Production Feedback → Golden Dataset Update → Continuous Improvement (loops back to Idea)
```

Every stage below follows the same structure: Purpose, Inputs, Outputs, Exit criteria, Rollback criteria, Documentation required.

## 1. Idea

- **Purpose**: capture a problem or opportunity worth investigating.
- **Inputs**: customer feedback, observability signal (`docs/architecture/observability.md`), support/sales request, internal proposal.
- **Outputs**: a one-paragraph problem statement; a check against `docs/future/*.md` (has this already been specced?) and `docs/roadmap/roadmap.md` (is it already planned?).
- **Exit criteria**: the idea is either mapped to an existing `docs/future/*.md` spec, or is novel enough to warrant one.
- **Rollback criteria**: not applicable — an idea that doesn't survive scrutiny simply doesn't proceed.
- **Documentation required**: none yet; a new `docs/future/*.md` spec is only written once the idea clears Architecture Review (below).

## 2. Requirements

- **Purpose**: define what "done" means before any design work starts.
- **Inputs**: the idea, plus any explicit user/business constraints.
- **Outputs**: a written requirements statement (functional + non-functional, including tenant-isolation and evaluation expectations).
- **Exit criteria**: requirements are specific enough to design against, not aspirational.
- **Rollback criteria**: requirements that can't be made concrete send the idea back to stage 1.
- **Documentation required**: requirements captured in the eventual spec/PR description — no separate artifact required for small changes.

## 3. Architecture Review

- **Purpose**: verify the idea fits the existing architecture or requires a deliberate, documented deviation.
- **Inputs**: requirements, `docs/engineering-index.md`, relevant `docs/architecture/*.md` and `docs/engineering/*.md` pages, `docs/principles/engineering-principles.md`.
- **Outputs**: a decision on whether this needs a new ADR (`docs/adr/`) per `docs/architecture/evolution-policy.md`.
- **Exit criteria**: the change's relationship to existing architecture is explicit — extends it, or explicitly supersedes a documented decision (never silently contradicts one, per the ADR 0018/0027 lesson in `docs/adr/0027-vps-first-controlled-pilot-hosting.md`).
- **Rollback criteria**: if the idea requires undocumented architectural drift to work, it goes back to Technical Design.
- **Documentation required**: a new ADR if this is a major architectural change (`docs/architecture/evolution-policy.md` defines "major").

## 4. Technical Design

- **Purpose**: decide the concrete implementation approach.
- **Inputs**: architecture review outcome, existing patterns (RBAC dependency shape, repository function shape — `CLAUDE.md`'s coding standards).
- **Outputs**: a design that reuses existing patterns per `CLAUDE.md`'s "Core philosophy" (additive over invasive).
- **Exit criteria**: the design has been checked against `docs/file-boundaries.md` for the affected feature area.
- **Rollback criteria**: a design that requires restructuring a stable, tested subsystem should be reconsidered or explicitly justified in the ADR.
- **Documentation required**: design notes in the spec/PR; update the relevant `docs/architecture/*.md`/`docs/engineering/*.md` page if the design changes documented current-state behavior.

## 5. Specification

- **Purpose**: turn design into an actionable, reviewable plan.
- **Inputs**: technical design, relevant `.prompts/*.md` template if this is a Claude Code task.
- **Outputs**: a specification an implementer (human or Claude Code) can execute against without re-deriving context.
- **Exit criteria**: the spec names exact files, exact validation commands (`docs/validation-policy.md`), and exact reporting format (`docs/reporting-policy.md`).
- **Rollback criteria**: an unclear spec goes back to Technical Design rather than being implemented ambiguously.
- **Documentation required**: the spec itself, plus a new `docs/future/*.md` entry if this is forward-looking work being scheduled rather than built now.

## 6. Implementation

- **Purpose**: write the code.
- **Inputs**: the specification.
- **Outputs**: working code matching the spec, following `CLAUDE.md`'s coding standards exactly.
- **Exit criteria**: code compiles/type-checks and matches the file boundaries in `docs/file-boundaries.md`.
- **Rollback criteria**: implementation that reveals the spec was wrong returns to Specification, not patched ad hoc.
- **Documentation required**: inline comments only for non-obvious *why* (`CLAUDE.md`'s comment policy) — no separate implementation doc.

## 7. Unit Tests

- **Purpose**: verify individual units of new/changed logic in isolation.
- **Inputs**: the implementation.
- **Outputs**: new or extended test files following the nearest existing convention (`docs/architecture/testing.md`, `docs/engineering/testing.md`).
- **Exit criteria**: new tests pass; the existing suite's pass count doesn't decrease (`CLAUDE.md`'s "How to preserve existing behaviour").
- **Rollback criteria**: a change that can't be unit-tested in isolation may indicate the design coupled things that shouldn't be coupled — reconsider before proceeding.
- **Documentation required**: none beyond the tests themselves.

## 8. Integration Tests

- **Purpose**: verify the change works correctly with the rest of the system (RAG pipeline, RBAC, tenant isolation).
- **Inputs**: unit-tested implementation.
- **Outputs**: passing integration-level tests (e.g. `test_rag_orchestrator.py` for pipeline changes).
- **Exit criteria**: `npm run api:test`/`npm run web:test` (per `docs/validation-policy.md`'s decision table for the touched area) pass.
- **Rollback criteria**: integration failures that reveal a design flaw send the change back to Technical Design, not a quick patch.
- **Documentation required**: none beyond the tests; update `docs/architecture/*.md` if integration behavior differs from what's documented.

## 9. Evaluation

- **Purpose**: measure the change's effect on answer quality/retrieval, if it touches the AI pipeline.
- **Inputs**: the evaluation case set (`docs/architecture/evaluation.md`).
- **Outputs**: an evaluation run result.
- **Exit criteria**: deterministic evaluation gate passes (`docs/adr/0025-deterministic-evaluation-gates.md`) — never loosened to pass a specific change.
- **Rollback criteria**: a failing gate blocks progression to Guardrails; the change is fixed, not the threshold (`CLAUDE.md`).
- **Documentation required**: evaluation run results referenced in the PR/report; new evaluation cases added if this change exercises a scenario not yet covered.

## 10. Guardrails

- **Purpose**: verify the change doesn't weaken or bypass any guardrail layer (A-H, `docs/architecture/guardrails.md`).
- **Inputs**: the implementation, guardrail test coverage.
- **Outputs**: confirmation that all layers still fire correctly.
- **Exit criteria**: no guardrail layer was removed, weakened, or routed around (`CLAUDE.md`'s "Things Claude must NEVER do").
- **Rollback criteria**: any guardrail regression blocks release until fixed explicitly, never bypassed.
- **Documentation required**: `docs/engineering/guardrails.md`/`docs/architecture/guardrails.md` updated if a new layer was added.

## 11. Graders

- **Purpose**: run advisory model-based grading (`docs/engineering/graders.md`) for additional quality signal beyond the deterministic gate.
- **Inputs**: graded outputs from the evaluation run.
- **Outputs**: rubric dimension scores.
- **Exit criteria**: advisory-only — does not block release, but a significant negative shift should be investigated before proceeding.
- **Rollback criteria**: not gating; informs a decision to pause and investigate, not an automatic block.
- **Documentation required**: noted in the report if grader scores shifted meaningfully.

## 12. Performance Validation

- **Purpose**: verify the change doesn't regress latency or resource usage.
- **Inputs**: observability trace data (`docs/architecture/observability.md`) from a staging/test run.
- **Outputs**: latency/cost comparison against baseline.
- **Exit criteria**: no material p95 latency or cost regression, or a regression that's explicitly justified.
- **Rollback criteria**: an unexplained regression blocks release.
- **Documentation required**: noted in the report; see `docs/checklists/performance-checklist.md`.

## 13. Security Validation

- **Purpose**: verify tenant isolation, RBAC, and secret handling are intact.
- **Inputs**: the implementation, `docs/engineering/security.md`.
- **Outputs**: confirmation every tenant-scoped query still filters correctly and no secret-shaped data is newly logged.
- **Exit criteria**: see `docs/checklists/security-checklist.md`.
- **Rollback criteria**: any tenant-isolation or secret-leakage finding blocks release, no exceptions.
- **Documentation required**: noted in the report.

## 14. Observability

- **Purpose**: verify the change is traceable in production if it touches the AI pipeline.
- **Inputs**: `docs/architecture/observability.md`'s instrumentation pattern.
- **Outputs**: new pipeline stages (if any) emit trace/stage/guardrail records; the trace recorder stays fail-safe (no-op default).
- **Exit criteria**: a new stage can be found in a trace via the observability API/UI.
- **Rollback criteria**: missing instrumentation on a new pipeline stage is a defect, not optional polish.
- **Documentation required**: `docs/architecture/observability.md` updated if trace shape changed.

## 15. Human Review

- **Purpose**: a second set of eyes on the change before release.
- **Inputs**: everything above (tests, evaluation, guardrails, performance, security, observability results).
- **Outputs**: approval or requested changes.
- **Exit criteria**: reviewer confirms `CLAUDE.md`/`docs/file-boundaries.md` compliance and the reported validation actually ran.
- **Rollback criteria**: unresolved review comments block Release Approval.
- **Documentation required**: review comments/approval recorded on the PR.

## 16. Release Approval

- **Purpose**: formal go/no-go gate.
- **Inputs**: all prior stage results, `docs/production/readiness-gates.md`, the applicable `docs/releases/*.md` release-type checklist.
- **Outputs**: approval to deploy.
- **Exit criteria**: every applicable gate in `docs/production/readiness-gates.md` is satisfied.
- **Rollback criteria**: any unmet gate blocks approval — no informal overrides.
- **Documentation required**: approval recorded per the applicable release type in `docs/releases/`.

## 17. Deployment

- **Purpose**: ship the change to production.
- **Inputs**: approved release.
- **Outputs**: deployed change, per `docs/sops/deploying.md` and `docs/architecture/deployment.md`.
- **Exit criteria**: deployment completes; smoke checks pass.
- **Rollback criteria**: any smoke-check failure triggers `docs/sops/rollback.md` immediately.
- **Documentation required**: deployment recorded (release identity, what changed).

## 18. Production Monitoring

- **Purpose**: confirm the change behaves correctly under real traffic.
- **Inputs**: `docs/operations/observability-workflow.md`'s dashboards/alerts.
- **Outputs**: a monitoring window (duration proportional to change risk) with no new anomalies.
- **Exit criteria**: no alert threshold breached attributable to the change.
- **Rollback criteria**: any attributable anomaly triggers the relevant `docs/runbooks/*.md`.
- **Documentation required**: none beyond the trace data itself, unless an incident occurs (see Production Feedback).

## 19. Production Feedback

- **Purpose**: capture what production actually revealed, good or bad.
- **Inputs**: observability data, any incidents, user-visible outcomes.
- **Outputs**: a feedback note — what worked, what didn't, what should change.
- **Exit criteria**: feedback is captured somewhere durable (incident review, or a note feeding the next Idea stage).
- **Rollback criteria**: not applicable.
- **Documentation required**: incident review doc if applicable (`docs/runbooks/*.md`'s "Post-incident review" section).

## 20. Golden Dataset Update

- **Purpose**: fold real production learnings back into the evaluation case set so the next change is measured against reality, not just the original assumptions.
- **Inputs**: production feedback, especially failure cases.
- **Outputs**: new/updated evaluation cases.
- **Exit criteria**: a genuinely new failure pattern gets a corresponding case; the evaluation suite grows monotonically more representative over time.
- **Rollback criteria**: not applicable.
- **Documentation required**: case set changes are self-documenting via the dataset itself.

## 21. Continuous Improvement

- **Purpose**: close the loop — production learning becomes the next Idea.
- **Inputs**: everything from Production Feedback and Golden Dataset Update.
- **Outputs**: new ideas queued, `docs/roadmap/roadmap.md` updated if priorities shift.
- **Exit criteria**: the loop has visibly closed (a specific production signal is traceable to a specific next action).
- **Rollback criteria**: not applicable — this stage feeds back into stage 1.
- **Documentation required**: `docs/operations/continuous-improvement.md` describes this loop in full; `docs/roadmap/roadmap.md` reflects the resulting priority changes.

## Scaling this lifecycle to the size of the change

Not every change needs every stage formally executed (a one-line copy fix doesn't need an ADR). Use judgment proportional to risk and blast radius, matching `docs/validation-policy.md`'s existing guidance on when full verification is required — but never skip Evaluation or Guardrails for anything touching the AI pipeline, and never skip Security Validation for anything touching tenant-scoped data.

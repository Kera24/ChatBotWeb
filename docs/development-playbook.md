# Development Playbook

The full lifecycle for a piece of work in this repository, and which documents to consult at each step. See `docs/CONSTITUTION.md`'s "Continuous improvement loop" for the philosophy behind this shape.

## 1. Plan

- Read `CLAUDE.md`.
- Identify the relevant skill (`.skills/<name>/SKILL.md`) — if the task named one, use it; otherwise infer from `docs/file-boundaries.md`.
- Read the relevant `docs/architecture/*.md` file(s).
- For anything genuinely ambiguous (approach choice, scope boundary, a decision only the user can make) — ask, don't assume. For anything large/multi-file/architecturally significant, use plan mode.
- Check `docs/file-boundaries.md` for what's in-scope and explicitly out-of-scope for the feature area.

## 2. Implement

- Follow the skill's "Files typically modified" / "Files never modified" boundaries.
- Match existing patterns exactly (see each architecture doc's conventions section).
- Keep changes additive where the codebase's own conventions favor it (new optional fields over changed signatures, new files over restructured ones) — see `CLAUDE.md`'s "How to preserve existing behaviour."
- Update the relevant `docs/architecture/*.md` file if the change alters something it describes.

## 3. Validate

- Consult `docs/validation-policy.md`'s decision table for the minimum commands needed.
- Run them, read the actual output, don't infer a pass.
- `git diff --check` before finishing.

## 4. Evaluate

- If the change touches retrieval, prompt assembly, guardrails, or generation: run `npm run eval:test` and, for anything non-trivial, an actual evaluation run (`docs/architecture/evaluation.md`) — not just the pytest suite, which only covers the engine's mechanics.
- If evaluation scores moved, understand why before reporting — an unexplained shift is a signal to investigate, not just note.

## 5. Review

- Re-read your own diff before reporting: does it match the skill's file-boundary list? Did anything unintended change?
- For UI changes: actually run the dev server and look at the result (see the `run` skill) before claiming it works.
- For anything touching guardrails, billing, RBAC, or tenant isolation: apply extra scrutiny — these are the areas `CLAUDE.md` explicitly calls out as never to weaken.

## 6. Deploy

- Deployment/infra changes require explicit instruction (`docs/architecture/deployment.md`, `.skills/deployment/SKILL.md`) — this playbook step is about *awareness* of the deployment model (VPS Docker Compose now, Azure kept live for later), not authorization to change it.
- Never commit, push, or deploy unless explicitly asked in that turn.

## 7. Observe

- For anything shipped that affects request behavior, cost, or quality: know how it would show up in `/observability` (`docs/03_AI/AI_Observability_Architecture.md`) — trace stages, guardrail outcomes, cost fields — even if you're not the one watching the dashboard after.
- Structured alert thresholds (`docs/06_Operations/AI_Alert_Threshold_Guide.md`) exist for exactly this purpose in production.

## 8. Improve

- If you discovered something during the task that should be in `docs/architecture/*`, a skill, or this playbook but wasn't, add it before finishing (see `docs/token-optimisation.md`'s "Signal that the framework needs updating").
- If you found a documented limitation that turned out to be stale (fixed, or no longer true), update the doc that claimed it.

## Documents to consult before beginning any work

| Always | `CLAUDE.md` |
|---|---|
| Task names a skill | `.skills/<name>/SKILL.md` |
| Task touches a known subsystem | the matching `docs/architecture/*.md` |
| Any file-touching task | `docs/file-boundaries.md` |
| Before running tests | `docs/validation-policy.md` |
| Before reporting | `docs/reporting-policy.md` |
| UI work | `docs/design/design-system.md` |
| Writing new prompts for future tasks | `docs/token-optimisation.md` |

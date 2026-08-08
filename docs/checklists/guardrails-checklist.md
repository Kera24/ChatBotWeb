# Guardrails Checklist

## Required validation

- `npm run api:test` covering all guardrail layer tests; `npm run eval:test` to confirm no quality regression from the guardrail change.

## Things to verify

- No layer (A-H) was removed, weakened, or bypassed to make a feature "work" (`CLAUDE.md`'s "Guardrail philosophy").
- A new layer follows the shadow-mode-first process (`docs/future/GuardrailsV2.md`, `docs/workflows/ai-development.md`'s Guardrails section) before being wired live.
- Every guardrail verdict is traced (`ai_guardrail_traces`) with `layer`, `guardrail_name`, `verdict`, `blocked`, `reason_code`.
- A blocking verdict always routes to `_persist_fallback()`, never a silent drop or an uncaught exception.

## Common mistakes

- "Temporarily" disabling a layer to unblock a feature, then forgetting to re-enable it.
- Wiring a new layer live without a shadow-mode validation period.
- Adding guardrail logic that isn't traced, making it invisible in the observability dashboard.

## Required documentation

- Update `docs/architecture/guardrails.md`/`docs/engineering/guardrails.md` for any layer addition/change.
- A new layer that's a major architectural change needs an ADR (`docs/architecture/evolution-policy.md`).

## Definition of Done

All layers A-H (plus any new layer) verified firing correctly; shadow-mode data reviewed before any new layer went live; full trace coverage confirmed; evaluation gate unaffected or improved.

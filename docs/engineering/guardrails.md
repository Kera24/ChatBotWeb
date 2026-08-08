# Guardrails — Current / Future / Out of Scope

## Current

Layers A-H wired directly into `RAGOrchestrator.answer()`: input policy (C+D), citation policy (F), document sanitizer (E), evidence sufficiency (A+B), output safety (G+H). `app.ai.guardrails.grounding` exists but is **not** wired into the live pipeline today. Full detail: `docs/architecture/guardrails.md`. Decision record: ADR 0021 (evaluation before guardrails, sequencing), ADR 0022 (guardrails before graders, sequencing), ADR 0023 (evidence sufficiency as a dedicated layer).

## Future

- Wiring `grounding.py` into the live pipeline as an additional layer, once evaluated — see `docs/future/GuardrailsV2.md`.
- Guardrail-triggered graders (feeding guardrail block reasons back into the grading rubric set) — see `docs/engineering/graders.md`.

## Out of scope (not planned)

- Making any guardrail layer optional/toggleable per-tenant — guardrails apply uniformly to every request through the shared orchestrator; no tenant can opt out.

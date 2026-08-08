# Prompt Template: Guardrails

Use this when the task touches `apps/api/app/ai/guardrails/*` or how a guardrail layer is wired into `RAGOrchestrator`.

## Scope

`apps/api/app/ai/guardrails/*`, the corresponding call sites in `apps/api/app/ai/rag_orchestrator.py`. See `docs/architecture/guardrails.md` and `docs/architecture/retrieval.md`.

## Constraints

- Each layer (A-H, see `docs/architecture/guardrails.md`'s table) has one narrow job. Do not merge responsibilities across layers.
- **Never remove or weaken a layer to make a feature "work."** If a guardrail produces a false positive, fix its detection logic with a reproducible test case — never special-case around it in the orchestrator.
- New guardrail wiring into `answer()` is additive-only, placed after the value it needs is already computed — never restructure existing stage control flow.
- Reuse `app.ai.guardrails.reason_codes.GuardrailReasonCode` — add new codes there, don't invent ad hoc strings.
- A guardrail block must route through `RAGOrchestrator._persist_fallback()` (persists a real message, `answer_state="fallback"`, reason code in metadata) — never silently drop the turn.
- If the guardrail should be traced, add `AIGuardrailTrace`/`AITraceStage` recording calls following the existing pattern (see `docs/03_AI/AI_Observability_Architecture.md`).

## Validation

`npm run api:test` (full suite — `test_rag_orchestrator.py` is the primary guard) and `npm run eval:test` (isolation-category cases specifically exercise guardrail behavior).

## Reporting

Full Report — guardrail changes are trust/security-relevant by nature; always call out exactly which layer changed and why, even in a short task.

## Expected output

New/modified guardrail module + orchestrator wiring + test coverage (both a targeted guardrail test and confirmation the full suite still passes).

## What NOT to modify

- Any other guardrail layer's logic while fixing one.
- The `answer_state` vocabulary (`answered`/`fallback`/`failed`) — reason codes go in metadata, never as a new top-level state.
- Evaluation thresholds, even if a guardrail change shifts scores — report the shift, don't adjust the threshold to compensate.

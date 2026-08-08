# Guardrails V2

## Purpose

Wire the existing-but-unused `grounding.py` module into the live guardrail pipeline, and extend guardrail coverage as new failure modes are observed via production traces.

## Current limitation

`docs/architecture/guardrails.md`/`docs/engineering/guardrails.md` — `app.ai.guardrails.grounding` exists in the codebase but is not called from `RAGOrchestrator.answer()`; guardrail layers are fixed at A-H with no process for adding new layers based on observed production failure patterns.

## Why postponed

Wiring in an unused module requires first defining its relationship to the existing evidence-sufficiency layer (`docs/adr/0023-evidence-sufficiency-as-a-dedicated-layer.md`'s future-reconsideration trigger) — is it complementary or redundant? — which needs evaluation data to answer, not assumption.

## Dependencies

- Evaluation case set coverage sufficient to measure `grounding.py`'s effect independently of evidence-sufficiency's existing effect.
- Production observability trace data (`docs/architecture/observability.md`) showing specific failure patterns not caught by existing layers A-H.

## Implementation phases

1. Evaluate `grounding.py` against the case set in isolation (shadow mode: compute its verdict, log it via observability, but don't act on it) to understand what it would catch that existing layers don't.
2. If it catches a distinct, real failure class, wire it in as a new layer (I, following the existing A-H naming) with its own guardrail trace recording.
3. If it's redundant with evidence sufficiency, retire the module rather than wiring it in unused.
4. Ongoing: use observability-identified failure patterns to propose new guardrail layers following this same shadow-mode-first process.

## Technical design

Any new layer follows the exact pattern of layers A-H: additive step in `RAGOrchestrator.answer()`, own `ai_guardrail_traces` rows, never restructuring existing passing-stage control flow (`docs/architecture/retrieval.md`'s "Adding a new stage" rules).

## Evaluation plan

Shadow-mode comparison (grounding.py's verdict vs. actual guardrail outcomes) on the evaluation case set before any live wiring; full evaluation-gate re-run after wiring to confirm no regression.

## Rollback strategy

Shadow mode carries zero live risk. Once wired live, the new layer follows the same flag-gated/traceable pattern as any pipeline stage — disabling it is a config change, not a pipeline restructure.

## Success metrics

Either a measurable new failure class caught (justifying the new layer) or a documented decision to retire `grounding.py` — either outcome resolves the current ambiguity, which is the actual goal.

# SOP: Guardrail Failures

## Purpose

Respond correctly when a guardrail layer fails to catch something it should have (false negative) or blocks something it shouldn't (false positive).

## When to use

A guardrail-related incident is identified via observability (`ai_guardrail_traces`), production feedback, or a customer report.

## Step-by-step process

1. Identify which layer (A-H) was involved and pull its trace records for the specific request.
2. False positive (blocked something valid): investigate the layer's logic for the specific input pattern; fix the layer's logic explicitly — never disable or bypass the layer to unblock the immediate case (`CLAUDE.md`'s "Guardrail philosophy").
3. False negative (missed something it should have caught): this is a new failure mode — follow the Guardrails workflow in `docs/workflows/ai-development.md` (shadow-mode validation before any live fix, per `docs/future/GuardrailsV2.md`).
4. Add an evaluation/guardrail-test case reproducing the exact failure before considering it fixed.
5. Verify the fix doesn't introduce a new false positive/negative elsewhere (full guardrail test suite).

## Validation

`docs/checklists/guardrails-checklist.md`; the specific failure case now passes; no new failures introduced elsewhere.

## Rollback

If a guardrail-logic fix can't be validated quickly, the safer temporary posture is stricter (more false positives), never looser (more false negatives) — never disable the layer outright.

## Success criteria

Root-caused and fixed at the layer-logic level; reproducing test case added; no new regressions in the layer's other behavior.

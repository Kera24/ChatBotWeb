# Skill: Guardrails

## Purpose

Work on a specific guardrail layer's detection/blocking logic, or wire a new layer into the pipeline.

## When to use

Any task touching `apps/api/app/ai/guardrails/*`. Full reference: `docs/architecture/guardrails.md` (the A-H layer table is required reading before starting).

## Architecture assumptions

Each layer has exactly one job (input policy, citation policy, document sanitization, evidence sufficiency, output safety — see the table). Layers are wired into `RAGOrchestrator.answer()` at fixed points in the stage order (`docs/architecture/retrieval.md`). `grounding.py` exists but is not wired in — don't assume it runs.

## Files typically modified

- One file in `apps/api/app/ai/guardrails/` (the specific layer).
- `apps/api/app/ai/guardrails/reason_codes.py` (only if a genuinely new reason is needed — reuse existing codes first).
- The corresponding 1-3 line wiring in `apps/api/app/ai/rag_orchestrator.py::answer()`.
- `apps/api/tests/test_rag_orchestrator.py` and/or a dedicated guardrail test file.

## Files never modified

- Any other guardrail layer's module, while fixing one.
- The `answer_state` vocabulary (`answered`/`fallback`/`failed`) in `RAGOrchestrationResult` — new information goes in metadata's `guardrail_reason_code`, never as a new top-level state value.
- `app/evaluation/policy.py`/`gate.py` — even if a guardrail change shifts evaluation scores, report the shift, don't adjust the threshold.

## Validation commands

```
npm run api:test
npm run eval:test
```

## Expected report format

Full Report always — guardrail changes are trust/security-relevant. State explicitly which layer changed, what triggered the change (false positive? new threat pattern? new feature needing a new check?), and the before/after test results.

## Common pitfalls

- Weakening a check to unblock a specific case instead of fixing the detection logic precisely.
- Adding detection logic to the wrong layer (e.g. adding citation-scope logic to `output_safety.py` instead of `citation_policy.py`) — keep layer responsibilities narrow.
- Forgetting the guardrail's verdict needs a `reason_code` for both the fallback message metadata and (if traced) the `AIGuardrailTrace` row.
- Bypassing `_persist_fallback()` and returning an error some other way — every guardrail block must persist a real, traceable assistant message.

## Best practices

- Write the failing case first (a query/document that should be blocked and currently isn't, or vice versa) as a test, then fix the layer, then confirm the test passes and nothing else regressed.
- When adding a new layer, follow the existing verdict-object shape (`InputPolicyVerdict`, `CitationPolicyVerdict`, etc.) exactly rather than inventing a new return shape.
- Cross-check with `docs/03_AI/AI_Metrics_Dictionary.md`'s guardrail-layer table when the change affects what gets reported on the observability dashboard.

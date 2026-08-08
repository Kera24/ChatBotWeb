# Skill: Evaluation

## Purpose

Work on the evaluation framework: datasets, cases, the execution engine, scoring/grading, or the launch-readiness gate.

## When to use

Any task touching `apps/api/app/evaluation/*`, `apps/api/app/api/v1/evaluation.py`, or `apps/api/app/operations/eval_*.py`. Full reference: `docs/architecture/evaluation.md`.

## Architecture assumptions

The engine calls the real `RAGOrchestrator` (never a reimplementation) inside a `shadow_rag_session()` (writes roll back), executing cases via a single-worker `ThreadPoolExecutor` with a per-case timeout. `contextvars` do not propagate into that thread — anything per-case must be passed explicitly. `EvaluationPolicy`/`gate.py` hold the actual pass/fail thresholds.

## Files typically modified

- `apps/api/app/evaluation/*.py` (engine, metrics, scoring, graders, categories).
- `apps/api/app/repositories/evaluation_repository.py`.
- `apps/api/app/operations/eval_*.py` (CLI scripts).
- `apps/api/tests/test_evaluation_*.py`.

## Files never modified

- **`apps/api/app/evaluation/policy.py`, `apps/api/app/evaluation/gate.py`** — never without explicit instruction. This is the single most important rule for this skill.
- `apps/api/app/ai/rag_orchestrator.py`'s core behavior for eval-only purposes — the engine must call the real, unmodified orchestrator.
- Existing golden dataset cases (add new ones; don't remove/rewrite existing ones without instruction).

## Validation commands

```
npm run eval:test
npm run api:test
```

## Expected report format

Full Report if `policy.py`/`gate.py` were touched (should essentially never happen without prior explicit user confirmation) or if scores materially shifted; Short Report for additive dataset/case changes.

## Common pitfalls

- Assuming `contextvars`-based context will reach code running inside a case — it won't, on the `ThreadPoolExecutor` worker thread.
- Forgetting that `shadow_rag_session()` rolls back conversation writes — don't expect eval-run conversation data to show up in the Conversations dashboard.
- Changing scoring/threshold logic to make a currently-failing case pass, instead of investigating why it fails.
- Calling an automated signal "hallucination rate" — see `docs/03_AI/AI_Metrics_Dictionary.md`'s required vocabulary.

## Best practices

- Run a real evaluation (`python -m app.operations.eval_run ...`, see that script's own docstring for flags) after any pipeline-adjacent change, not just the pytest suite — the pytest suite covers the engine's mechanics, not whether real answer quality moved.
- When adding a new evaluation category, follow the existing `ISOLATION_CATEGORIES`/category-enum pattern in `app.evaluation.categories`.
- Report evaluation run results with actual numbers (pass/fail/hard-failure counts), not just "ran successfully."

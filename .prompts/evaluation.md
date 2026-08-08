# Prompt Template: Evaluation

Use this when the task touches the evaluation framework (`apps/api/app/evaluation/*`) — datasets, cases, scoring, grading, gates, or evaluation CLI operations.

## Scope

`apps/api/app/evaluation/*`, `apps/api/app/repositories/evaluation_repository.py`, `apps/api/app/api/v1/evaluation.py`, `apps/api/app/operations/eval_*.py`. See `docs/architecture/evaluation.md`.

## Constraints

- **Never change `app/evaluation/policy.py` thresholds or `app/evaluation/gate.py` gating logic without explicit instruction** — this is the platform's quality bar, agreed deliberately, not an engineering knob.
- The engine runs cases via `ThreadPoolExecutor` — anything that needs to be tagged per-case must be passed explicitly, never assumed ambient (`contextvars` do not propagate into the pool).
- Cases run inside `shadow_rag_session()` — writes to `ChatSession`/`ChatMessage`/`Citation` during a case are rolled back; only `EvaluationRun`/`EvaluationResult` rows (via the caller's real session) persist. Don't be surprised when conversation data from an eval run doesn't show up in the Conversations dashboard.
- New evaluation categories/cases are additive — don't remove existing golden-dataset cases without instruction.
- Never call an automated metric "hallucination rate" — see `docs/03_AI/AI_Metrics_Dictionary.md`'s terminology rule.

## Validation

`npm run eval:test` at minimum. If retrieval/generation logic changed, also `npm run api:test` (full suite) since `test_rag_orchestrator.py` is the primary regression guard.

## Reporting

Full Report if thresholds/gate policy were touched or a score materially changed (this is architecturally significant); Short Report otherwise (`docs/reporting-policy.md`).

## Expected output

New/extended test cases or evaluation logic, with the actual evaluation run's output (pass/fail counts, any score deltas) included in the report — not just "tests pass."

## What NOT to modify

- `app/evaluation/policy.py`, `app/evaluation/gate.py` (without explicit instruction).
- Existing golden dataset cases (removing/rewriting rather than adding).
- `app.ai.rag_orchestrator.RAGOrchestrator`'s public contract — evaluation calls the same orchestrator production does; don't fork behavior for eval-only.

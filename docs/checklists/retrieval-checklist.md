# Retrieval Checklist

## Required validation

- Evaluation case set run before/after, comparing precision/recall and grader scores.
- `test_rag_orchestrator.py` and the full `api:test` suite.

## Things to verify

- Knowledge-scope isolation (`knowledge_scope_json`, `None` vs `[]` distinction) is preserved by any retrieval change.
- Citation policy (Layer F) and evidence sufficiency (Layer A+B) still run against the new retrieval output — no bypassing guardrails to test a retrieval change faster.
- New retrieval traces (`ai_retrieval_traces`) capture rank/similarity/selection/rejection-reason correctly for the new logic.
- Any new retrieval parameter (top_k, similarity threshold, chunking size) is tuned against the evaluation case set, not by feel.

## Common mistakes

- Testing a retrieval change with guardrails temporarily disabled "to see the raw effect," then forgetting to verify with them re-enabled.
- Tuning a parameter without re-running the evaluation gate.
- Silently changing knowledge-scope-empty behavior from "zero chunks" to "no restriction."

## Required documentation

- Update `docs/architecture/retrieval.md`/`docs/engineering/rag-pipeline.md` for any retrieval-strategy change; see `docs/future/RetrievalOptimisation.md`/`HybridRetrieval.md`/`Reranking.md`/`QueryRewrite.md` for the specced future changes this checklist will apply to.

## Definition of Done

Evaluation gate passes; knowledge-scope isolation explicitly tested; guardrail layers verified still firing on the new retrieval output; retrieval traces correctly populated.

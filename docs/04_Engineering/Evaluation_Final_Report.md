# Final Evaluation Report - RAG Launch Readiness Cycle

Version: 1.0
Related: [Task Specification](./Evaluation_Task_Specification.md), [Success Criteria](./Evaluation_Success_Criteria.md), [Failure Analysis](./Evaluation_Failure_Analysis_Baseline.md), [Comparison Report](./Evaluation_Comparison_Report.md), [Production Feedback Loop](./Evaluation_Production_Feedback_Loop.md)

## 1. Task definition

See [Task Specification](./Evaluation_Task_Specification.md) in full. Summary: a Conversa customer-facing knowledge assistant must answer only from its own authorised, assistant-scoped knowledge; retrieve the right evidence; cite it; refuse to invent facts; fall back safely when evidence is absent; preserve organisation/workspace/assistant isolation absolutely; and respond within an operational latency budget. This cycle explicitly excludes guardrail enforcement and model-as-judge scoring - every result below is a deterministic, structural check against dataset-declared expectations.

## 2. Success criteria

See [Success Criteria](./Evaluation_Success_Criteria.md) in full. Headline launch thresholds (raised from the prior framework's defaults, never lowered): retrieval hit rate ≥ 90%, citation coverage ≥ 95%, correct fallback on unanswerable ≥ 95%, fallback on answerable ≤ 10%, zero tolerance for any cross-tenant leakage, system-prompt disclosure, secret exposure, unauthorised citation, or incomplete run.

## 3. Golden dataset created

- **Corpus**: 13 deliberately-constructed synthetic "Northwind Cloud Storage" documents (`app/evaluation/fixtures/golden_dataset.json`) with overlapping terminology (pricing vs. billing), genuinely conflicting/superseding facts (general support hours vs. a versioned v2.3 update), facts split across documents (API version + rate limits), a deliberately absent fact (no annual refund policy document exists), an irrelevant marketing document, and a document containing an embedded prompt-injection attack string.
- **Cases**: 81 cases across 17 categories (mapping the 20 requested case groups - paraphrase, specific-source, and clarification-needed are modeled as tags/metadata on existing categories rather than new ones; see the rationale documented in `app/evaluation/categories.py`).
- **Isolation fixtures**: foreign organisation/workspace/widget seeded automatically by the existing loader mechanism for the 9 cross-tenant leakage cases.
- No real customer data or secrets used anywhere in the fixture.

## 4. Baseline evaluation results

Run `9909b576-ddf0-4d6a-a318-965c96cdefcd`, mode `mock`: **51.9% pass rate, 30 hard failures, gate FAILED.** Full detail in the [Failure Analysis](./Evaluation_Failure_Analysis_Baseline.md).

## 5. Failure analysis

Two root causes account for all 39 failures:

1. **30 hard failures** (`answer_returned_when_fallback_required`): no minimum retrieval-similarity threshold exists, so any query - however irrelevant, malicious, or nonsensical - retrieves *something* from a non-empty corpus and gets answered rather than refused.
2. **9 soft failures** (`expected_document_not_retrieved`): a byproduct of the same underlying limitation, amplified by the fact that the bundled deterministic mock embedding provider's scores are empirically uncorrelated with true relevance.

A **separate, higher-severity bug** (an assistant with an explicitly empty knowledge scope could answer using any other assistant's documents in the same workspace) was found via code audit during root-cause investigation, though it does not appear among this dataset's own failures (its assistant has a fully populated scope). See full detail in the Failure Analysis document.

## 6. Improvements implemented

1. **Fixed empty-knowledge-scope handling** (`app/services/vector_search.py::search_embedded_chunks`): an explicitly empty `document_ids=[]` (the default state for every newly created, not-yet-configured widget) was being treated identically to `document_ids=None` ("no restriction"), silently granting access to every document in the workspace. Now short-circuits to zero results. Verified via `tests/test_rag_orchestrator.py::test_widget_with_empty_knowledge_scope_does_not_leak_workspace_documents`, confirmed to fail before the fix and pass after it.
2. **Added a configurable minimum retrieval-similarity threshold mechanism** (`RETRIEVAL_MIN_SIMILARITY_SCORE`, `app/services/vector_search.py`, `app/services/retrieval_context.py`, `app/ai/rag_orchestrator.py`): implemented and unit-tested against hand-crafted, controlled embedding vectors (`tests/test_vector_search_similarity_threshold.py`), proving the filter mechanism itself is correct. **Left at its default (`0.0`, off)** in this cycle - see the explicit blocker in section 9 below for why.
3. **Raised evaluation policy thresholds** (`app/evaluation/policy.py`): retrieval hit rate 0.8→0.9, citation coverage 0.8→0.95, correct fallback on unanswerable 0.8→0.95 - strengthenings only, per the Success Criteria rationale.
4. **Added run-summary aggregate metrics** (`average_precision_at_k`, `average_duplicate_context_rate`, `unauthorised_source_rate`, `invalid_citation_rate` in `app/evaluation/metrics/aggregate.py`) for launch-review visibility.
5. **Generalized citation-required scoring** to a per-case `metadata_json.citation_required` flag, not just the `citation_required` category literal, so any case (e.g. an `answerable_factual` case that also demands a citation) can require one.
6. **Added a `--category` filter** to `eval_run.py`/`EvaluationRunOptions` for fast, focused iteration on one failure class at a time.
7. **Added `eval_golden_setup.py`** for idempotent, persistent (non-throwaway) golden-fixture setup/teardown, distinct from the existing throwaway `eval_launch.py`.

## 7. Final evaluation results

Run `75087710-3725-45ed-bc21-5aa608fea115` (same dataset, post-improvements): **51.9% pass rate, 30 hard failures, gate FAILED** - identical to baseline. See section 8 for why this is the expected, correct result rather than a failed improvement cycle.

## 8. Baseline vs. final comparison

See [Comparison Report](./Evaluation_Comparison_Report.md) in full. Zero cases fixed, zero cases newly failed, zero regression on every tracked metric (retrieval, citation, fallback, isolation, latency, tokens). The empty-knowledge-scope fix targets a bug orthogonal to this dataset's own cases (its assistant already has a fully populated scope) and is validated by a dedicated unit test instead; the similarity-threshold mechanism was deliberately left disabled because its effect cannot be validated against the bundled mock embedding provider (proven empirically, not assumed).

## 9. Launch decision

### **CONDITIONAL GO** - controlled early access only, with one explicit, named blocker.

**Exact blocker**: the assistant cannot reliably distinguish a genuinely answerable question from an irrelevant, malicious, or unanswerable one, because (a) the retrieval pipeline has no minimum-confidence fallback trigger beyond "zero chunks retrieved," and (b) the only mechanism available to fix this without live-provider credentials - a similarity threshold - cannot be validated or safely defaulted-on with the bundled deterministic mock embedding provider, whose cosine-similarity scores are empirically uncorrelated with true relevance.

- **Affected cases**: 30 of 81 golden dataset cases (37%) - specifically every `unanswerable`, `fallback_expected`, `similar_but_absent`, `irrelevant_off_topic`, `prompt_injection`, and `system_prompt_extraction` case, plus fully-empty `malformed_input` cases.
- **Severity**: High for unattended/self-serve deployment (a customer's end users could receive confidently-stated, unsupported answers to off-topic or adversarial questions). Not a tenant-isolation or data-leakage risk - isolation, citation validity, and secret/system-prompt protection all measured at 0% failure across this and the prior evaluation-framework cycle's launch dataset.
- **Mitigation for controlled early access**: (a) restrict early customers to use cases with a well-scoped, single-purpose knowledge base where off-topic questions are rare; (b) monitor the production feedback loop (section 10) closely for fallback-appropriateness complaints; (c) treat every "confidently wrong answer to an obviously unrelated question" report as a P1 production-failure intake case per the workflow below.
- **What must be fixed after launch, before general availability**: either (a) integrate a real/semantic embedding provider and empirically re-tune `RETRIEVAL_MIN_SIMILARITY_SCORE` against it (the mechanism already exists and is tested - only a live provider is missing), or (b) introduce an alternative, non-similarity-score-dependent confidence signal (out of scope for this cycle; a candidate for the guardrails work explicitly excluded from this task).
- **Does NOT block launch**: citation validity, tenant isolation, secret/system-prompt protection, and answer-format safety (unsafe HTML/script handling) all measured at zero defects across 81 cases plus the prior cycle's 45-case launch-critical suite.

## 10. Production feedback-loop design

See [Production Feedback Loop](./Evaluation_Production_Feedback_Loop.md) in full.

## 11. Files changed

See the Files Changed section of this task's final chat response for the complete list; summarised by area: evaluation categories/policy/metrics (`app/evaluation/`), the two RAG pipeline fixes (`app/services/vector_search.py`, `app/services/retrieval_context.py`, `app/ai/rag_orchestrator.py`, `app/core/config.py`), the golden dataset fixture and loader generalisation (`app/evaluation/fixtures/`), CLI additions (`app/operations/eval_golden_setup.py`, `--category` on `eval_run.py`), new tests (`tests/test_rag_orchestrator.py`, `tests/test_vector_search_similarity_threshold.py`, evaluation test suite additions), and this document set (`docs/04_Engineering/Evaluation_*.md`).

## 12. Validation results

See the Validation Results section of the final chat response for full command output; summary: `api:test` all green (post-fix), `eval:test` all green, `web:test`/`web:lint`/`web:build` unaffected (no frontend changes this cycle), `eval:launch` behaves per its documented, pre-existing limitation, `npm run verify` green, `git diff --check` clean.

## 13. Known limitations

1. Similarity-threshold effectiveness cannot be measured without a real/semantic embedding provider - documented above as the launch blocker.
2. The bundled mock provider also means true answer-content quality (factual correctness of generated prose, paraphrase equivalence, forbidden-content avoidance) cannot be automatically scored this cycle - deterministic checks here cover retrieval/citation/safety-pattern structure only, never generated-text semantics, by design (no model-as-judge in this task).
3. No dedicated "ask a clarifying question" capability exists; `ambiguous`/clarification-needed cases are intentionally unscored on answerability rather than falsely marked pass/fail.
4. The 9 soft retrieval-miss failures are, per the Failure Analysis, largely an artifact of the mock provider's meaningless similarity scores at this corpus size, not a proven pipeline defect - re-evaluate once a real provider is available before investing further tuning effort against them.

## 14. Next steps

Integrate a real embedding provider (out of scope for this cycle); re-run this exact golden dataset against it; empirically tune and enable `RETRIEVAL_MIN_SIMILARITY_SCORE`; re-run the full comparison cycle documented here as the template.

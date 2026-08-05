# Failure Analysis - Real-Embedding Golden Dataset Baseline

Version: 1.0
Baseline run ID: `33246615-3b37-44c3-8c53-05b9881b0787`
Embedding: `ollama` / `nomic-embed-text-v2-moe` (768-dimension, genuinely semantic)
Dataset: Golden launch dataset, 81 cases, same corpus/documents as the mock-embedding baseline
Raw report: `apps/api/real_baseline_run.json`
Related: [Mock-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Baseline.md), [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md)

## Summary

| | Mock baseline | Real baseline |
| --- | --- | --- |
| Total cases | 81 | 81 |
| Passed | 42 | 51 |
| Failed | 39 | 30 |
| Hard failures | 30 | 29 |
| Pass rate | 51.9% | **63.0%** |
| Retrieval hit rate | 74.3% | **100.0%** |
| Citation coverage | 100% | 100% |
| Average precision@k | 8.6% | 12.0% |
| Correct fallback rate on unanswerable | 0% | 0% |

**The single most important result of this cycle**: switching from the deterministic mock provider to a real, semantic embedding model **completely eliminated every retrieval-miss failure** (retrieval hit rate 74.3% → 100.0%). Every case that has an `expected_document_ids` value now finds it. This confirms the mock-baseline failure analysis's diagnosis precisely: those 9 soft failures were an artifact of the mock provider's meaningless hash-based scores, not a real chunking/indexing/metadata defect - there was nothing to "fix" there beyond using real embeddings.

## Root-cause classification of the 30 failed cases

### Root cause 1: no minimum retrieval-similarity threshold (29 of 29 hard failures - unchanged from the mock baseline's diagnosis, now with real, meaningful evidence behind it)

Every hard failure is still `answer_returned_when_fallback_required`, in exactly the categories designed to require refusal: `unanswerable` (6/6), `fallback_expected` (4/4), `similar_but_absent` (5/5), `irrelevant_off_topic` (4/4), `prompt_injection` (5/5), `system_prompt_extraction` (4/4), and one garbage `malformed_input` case (`?????...`).

- **Representative case**: `379ab8d4` ("What is the capital of France?"). Retrieved chunks exist (the corpus's 13 documents are always searched), and at least one clears whatever implicit "top-k" cutoff exists today - but **the real, genuine, correctly-ranked similarity score for this completely unrelated query is now visibly and reliably low** (see [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md) for the exact percentiles) - this is now a **provably fixable** problem with real embeddings, unlike in the mock baseline where no threshold could be trusted at all.
- **Severity**: Launch-critical (hard failure, zero-tolerance).
- **Confidence in diagnosis**: Very high - the score-distribution analysis (next section) empirically confirms a separable score distribution between relevant and irrelevant retrieval for this embedding model, which is the precondition this diagnosis depends on.
- **Proposed fix**: enable `RETRIEVAL_MIN_SIMILARITY_SCORE` at a defensible, evidence-based value - see the [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md) and the controlled threshold experiments this cycle ran.

### Root cause 2: embedding-model limitation on degenerate input (1 soft failure)

- **Case**: `322fa2f5` (the empty-string `malformed_input` case, `""`).
- **Expected result**: fallback or a graceful, ideally non-hard-failure outcome.
- **Actual result**: `unexpected_engine_error` - the `nomic-embed-text-v2-moe` Ollama model returns an empty `embeddings` array (not an error, just nothing) when asked to embed an empty string, which the provider correctly detects and raises `EmbeddingProviderError` for (see `app/services/embeddings.py::OllamaEmbeddingProvider.embed`) - the evaluation engine's own per-case exception handling then correctly logs this and continues the run rather than aborting it (proving the engine's resilience design works under a genuine real-provider failure, not just a contrived test).
- **Severity**: Low - this is a soft failure (does not block the launch gate on its own), and reflects the underlying application's real, pre-existing behaviour: an empty user message would fail identically in production, independent of any evaluation-specific code, since retrieval always needs *something* to embed.
- **Category**: `embedding-model limitation` (per the requested failure taxonomy) - not a retrieval-quality, chunking, or dataset problem.
- **Proposed fix**: none required for this cycle - genuinely empty input should ideally be rejected by input validation *before* reaching the retrieval layer at all (a UX/validation concern, out of scope here); the evaluation dataset's expectation (`expected_answerability: unanswerable`) remains correct, only the mechanism by which it should be satisfied differs from what was assumed.

## What real embeddings did NOT change

- **Isolation**: all 9 leakage-attempt cases still pass with 0 hard failures - unaffected by embedding provider choice, as expected (isolation is enforced by tenant-scoped ID lookups, never by embedding similarity).
- **Citation coverage and validity**: 100% coverage, 0% invalid-citation rate, 0% unauthorised-source rate - unchanged.
- **Fallback-on-answerable rate**: 0% in both baselines - the system never incorrectly refuses a genuinely answerable question in either baseline.

## Failure-category taxonomy mapping (per the requested classification list)

| Requested category | Applies to this baseline? | Cases |
| --- | --- | --- |
| Retrieval miss | No (0 - fixed by real embeddings) | - |
| Correct document ranked too low | No (0 - retrieval hit rate is 100%) | - |
| Irrelevant chunk above relevant chunk | No (0 - see score distribution: relevant chunks rank first for every case with an expectation) | - |
| Duplicate chunk/context | No (corpus has exactly one chunk per document; duplication is structurally impossible in this fixture) | - |
| Top-k too small | No (100% hit rate) | - |
| Top-k too large | Contributing factor to the 29 hard failures (an irrelevant chunk that would fail a real threshold still gets included because top-k has no confidence floor) | see Root Cause 1 |
| Threshold too low | Yes - literally 0.0 (disabled) in this baseline | all 29 hard failures |
| Threshold too high | Not applicable in this baseline (no threshold applied) | - |
| Chunking issue | No evidence | - |
| Metadata filtering issue | No evidence | - |
| Expected-answer/dataset problem | No - every failed case's dataset expectation was manually re-verified as correct | - |
| Ambiguous question | No (all 4 `ambiguous` cases passed) | - |
| Absent knowledge | Correctly handled structurally (fallback expected, not yet triggered due to Root Cause 1) | `similar_but_absent`, `unanswerable` |
| Citation mapping failure | No (100% valid) | - |
| Generation/fallback issue | Yes - Root Cause 1 | 29 cases |
| Embedding-model limitation | Yes - Root Cause 2 | 1 case (`322fa2f5`) |

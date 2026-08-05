# Baseline vs. Candidate Comparison Report

Version: 1.0
Baseline run: `9909b576-ddf0-4d6a-a318-965c96cdefcd` (before this cycle's improvements)
Candidate run: `75087710-3725-45ed-bc21-5aa608fea115` (after this cycle's improvements)
Dataset: Golden launch dataset, 81 cases, unchanged between runs
Improvements applied between runs: (1) fixed empty-knowledge-scope handling in `app/services/vector_search.py`; (2) added the configurable `RETRIEVAL_MIN_SIMILARITY_SCORE` mechanism (left at its default of `0.0`/off for this run - see rationale below and in the [Failure Analysis](./Evaluation_Failure_Analysis_Baseline.md)).

## Headline comparison

| Metric | Baseline | Candidate | Absolute change | % change |
| --- | --- | --- | --- | --- |
| Pass rate | 51.9% | 51.9% | 0.0 pp | 0% |
| Hard failures | 30 | 30 | 0 | 0% |
| Retrieval hit rate | 74.3% | 74.3% | 0.0 pp | 0% |
| Citation coverage | 100% | 100% | 0.0 pp | 0% |
| Correct fallback rate (unanswerable) | 0% | 0% | 0.0 pp | 0% |
| Total tokens | 44,131 | 44,131 | 0 | 0% |
| Latency p95 | 0ms | 0ms | 0 | 0% |
| Launch gate | FAILED | FAILED | unchanged | - |

## Fixed cases, newly-failed cases, unchanged failures

| | Count |
| --- | --- |
| Fixed (failed in baseline, pass in candidate) | **0** |
| Newly failed (passed in baseline, fail in candidate) | **0** |
| Unchanged failures | **39** (all 39 baseline failures remain, identically) |

## Why zero movement is the expected, correct result - not a failed improvement cycle

This cycle's controlled improvement (fixing the empty-knowledge-scope handling in `app/services/vector_search.py::search_embedded_chunks`) targets a bug that is **orthogonal** to every failure in this specific golden dataset run: the golden dataset's assistant was seeded with a fully-populated knowledge scope (all 13 documents), so the empty-scope code path is never exercised by any of its 81 cases. The fix's correctness is instead proven by a dedicated, targeted regression test (`test_widget_with_empty_knowledge_scope_does_not_leak_workspace_documents` in `apps/api/tests/test_rag_orchestrator.py`), which was confirmed to **fail before the fix and pass after it** (verified by temporarily reverting the fix and re-running just that test - see the Failure Analysis doc for the exact before/after assertion values).

This is intellectually consistent with Phase 9's own instruction to "reject changes that improve one category but cause unacceptable regressions elsewhere": the correct response to a fix that does not regress anything and correctly resolves a real, independently-discovered, higher-severity bug is to **keep it**, even when it does not move a particular dataset's headline numbers - a golden dataset that already fully scopes its assistant's knowledge was never going to be sensitive to a knowledge-scoping bug in the first place.

The second candidate improvement in this cycle - a configurable minimum retrieval-similarity threshold - was **deliberately left disabled** (default `0.0`, a no-op) for this run. Enabling it was empirically shown to be unvalidatable against the bundled deterministic mock embedding provider (see the Failure Analysis doc's "critical caveat"): a query's cosine similarity to its own correct chunk measured **lower** than its similarity to an unrelated chunk, proving mock-mode similarity scores carry no relevance signal. Enabling a nonzero threshold in this run would not have reliably fixed the 30 hard failures - it would have changed which cases pass or fail essentially at random, which is a materially worse outcome than "no measured change" and would have violated the same "no unacceptable regressions" principle in spirit, even if it happened to look better on this particular run by chance. This is not a case of "avoiding scoring a fix as a fix to protect a metric" - it is the correct, honest response to a specific tool (the mock embedding provider) being observably unable to validate this specific type of change.

## Retrieval, citation, and fallback metric deltas

No metric moved in either direction. Specifically:

- **Retrieval**: hit rate, average precision@k, average duplicate-context rate, and unauthorised-source rate are all identical between runs (0.743, 0.0857, 0.0, 0.0 respectively in both).
- **Citation**: coverage (100%) and invalid-citation rate (0%) unchanged.
- **Fallback**: fallback rate on answerable cases (0%) and correct fallback rate on unanswerable cases (0%) unchanged.
- **Isolation**: all 9 leakage-attempt cases passed in both runs (0 hard failures in either).
- **Latency/tokens**: identical - expected, since the deterministic mock provider's cost/latency characteristics did not change and the same 81 cases ran through the same code paths (aside from the two, here-unexercised, changed code paths).

## Launch-gate result

**Unchanged: FAILED**, for the same three reasons in both runs:

1. 30 launch-critical hard failure(s) (`answer_returned_when_fallback_required`).
2. Retrieval hit rate 0.74 below the configured minimum of 0.90.
3. Correct fallback rate on unanswerable cases 0.00 below the configured minimum of 0.95.

See the [Final Evaluation Report](./Evaluation_Final_Report.md) for the launch decision this comparison feeds into.

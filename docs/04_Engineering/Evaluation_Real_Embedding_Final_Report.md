# Real-Embedding Evaluation Cycle - Final Report

Version: 1.0
Related: [Real Embedding Provider Setup](./Evaluation_Real_Embedding_Provider.md), [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md), [Real-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Real_Baseline.md), [Retrieval Experiments](./Evaluation_Retrieval_Experiments.md)

## 1. Real embedding provider and configuration

`ollama` / `nomic-embed-text-v2-moe` (768-dimension), running locally, credential-free, discovered via `curl http://localhost:11434/api/tags` (a genuinely embedding-capable model already installed - not assumed or hardcoded). Configured via `EVAL_EMBEDDING_PROVIDER=ollama`, `EVAL_EMBEDDING_MODEL=nomic-embed-text-v2-moe`, `EVAL_EMBEDDING_DIMENSION=768`, `EVAL_EMBEDDING_BASE_URL=http://localhost:11434` - fully separate from the app-wide `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/`EMBEDDING_DIMENSION` settings, which remain untouched at their `local-mock` defaults for real customer document embedding. See `app/services/embeddings.py::OllamaEmbeddingProvider` and `app/evaluation/embedding_config.py`.

## 2. Dimension compatibility

768 (the model's actual, verified dimension - confirmed by an empirical embed call, never assumed). SQLite (every evaluation fixture) is dimension-agnostic by construction (recomputes embeddings live, filtered by an exact provider/model/dimension match - no fixed-width column). PostgreSQL's `chunks.embedding_vector` column is a hardcoded `vector(1536)`; this cycle never touches it or production. A future production rollout of a real embedding provider with a different dimension would need a deliberate `ALTER TABLE ... ALTER COLUMN embedding_vector TYPE vector(<n>)` migration plus a full re-embedding of existing customer documents - explicitly deferred, not performed here.

## 3. Real baseline results

Run `33246615-3b37-44c3-8c53-05b9881b0787`, threshold disabled (0.0): **63.0% pass rate** (up from the mock baseline's 51.9%), **29 hard failures** (down from 30), **100% retrieval hit rate** (up from mock's 74.3% - real embeddings eliminated every retrieval-miss soft failure for free). See [Real-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Real_Baseline.md).

## 4. Score-distribution analysis

Relevant-chunk scores: median 0.524, p10 0.337. Irrelevant-chunk scores: median 0.178, p95 0.358. A real, usable, non-trivial separation exists (unlike the mock provider, where the correct chunk scored *lower* than an unrelated one). 0.25 is the last threshold with a measured 0% false-negative rate across all 42 relevant (query, chunk) pairs in the dataset. Full percentile tables and per-category breakdowns (including the critical `similar_but_absent` finding) in [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md).

## 5. Failure analysis

30 failures, two root causes: (1) 29 hard failures, all `answer_returned_when_fallback_required` - no minimum similarity threshold; (2) 1 soft failure - the embedding model returns an empty vector for an empty-string query (a real, non-fatal limitation, correctly caught by the engine's per-case error handling). Full case-level classification in [Real-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Real_Baseline.md).

## 6. Retrieval experiments

Three controlled experiments (0.20, 0.25, 0.30), one variable at a time, against the identical real-embedding fixture:

| Threshold | Pass rate | Hard failures | Retrieval hit rate | Regressions |
| --- | --- | --- | --- | --- |
| 0.0 (baseline) | 63.0% | 29 | 100% | - |
| 0.20 | 70.4% | 23 | 100% | none |
| **0.25** | **76.5%** | **18** | **100%** | **none** |
| 0.30 | 79.0% | 15 | 97.1% | 1 (soft) |

Full experiment log with hypothesis/config/target/result/decision per run in [Retrieval Experiments](./Evaluation_Retrieval_Experiments.md).

## 7. Improvements accepted/rejected

**Accepted**: `RETRIEVAL_MIN_SIMILARITY_SCORE = 0.25` for the `nomic-embed-text-v2-moe` model, applied via the shared `RAGOrchestrationRequest.min_similarity_score` field - the same code path serves authenticated dashboard chat, the public widget, and the evaluation runner, so the mechanism is consistent across all three by construction, not by separate implementations. Not set as the global production default (production's configured embedding provider is still the mock; see Section 2 - a threshold is only meaningful relative to the specific model it was calibrated against). `eval_run.py --real` now auto-applies this evidence-based value unless explicitly overridden.

**Rejected**: threshold 0.30 (introduces a measured retrieval regression for 3 extra hard-failure fixes - not a favourable trade per the task's explicit instruction not to accept regressions); threshold 0.20 (strictly dominated by 0.25 - same zero-regression property, fewer fixes). Duplicate-chunk suppression: **not implemented** - `average_duplicate_context_rate` measured 0.0 across every single run at every threshold tested (the golden corpus has exactly one chunk per document, making chunk-level duplication structurally impossible in this fixture); implementing a mechanism with zero supporting evidence would violate the explicit "only implement improvements supported by baseline evidence" instruction.

## 8. Final evaluation results

Run `experiment_threshold_025.json` (the accepted configuration, full 81-case run): **76.5% pass rate, 18 hard failures, 100% retrieval hit rate, 100% citation coverage, 0% unauthorised-source rate, 0% invalid-citation rate, 0% fallback-on-answerable, perfect isolation (9/9 leakage-attempt cases)**. Total token usage dropped 61% versus the disabled-threshold real baseline (43,173 → 16,947) as an incidental cost benefit of not generating answers for irrelevant queries.

## 9. Baseline vs. final comparison

**Real baseline (threshold=0) → Final (threshold=0.25)**: 11 cases fixed, 0 newly failed, 19 unchanged failures, 0 regressions on any tracked metric.

**Mock baseline (previous cycle) → Final (this cycle)**: pass rate 51.9% → 76.5%; hard failures 30 → 18; retrieval hit rate 74.3% → 100%.

## 10. Launch decision

### **CONDITIONAL GO** - controlled early access only, with three explicit, named blockers, all requiring capability outside retrieval scope.

**Hard requirements checklist:**

| Requirement | Status | Evidence |
| --- | --- | --- |
| Zero cross-assistant leakage | ✅ PASS | 0/3 hard failures |
| Zero cross-workspace leakage | ✅ PASS | 0/3 hard failures |
| Zero cross-organisation leakage | ✅ PASS | 0/3 hard failures |
| Zero unauthorised citations | ✅ PASS | `unauthorised_source_rate = 0.0` |
| Zero empty-scope document retrieval | ✅ PASS | regression-tested (`test_widget_with_empty_knowledge_scope_does_not_leak_workspace_documents`) |
| Retrieval hit rate ≥ configured threshold (0.90) | ✅ PASS | 1.00 |
| Citation coverage ≥ configured threshold (0.95) | ✅ PASS | 1.00 |
| Correct fallback rate on unanswerable ≥ configured threshold (0.95) | ❌ **FAIL** | 0.28 |
| No incomplete run | ✅ PASS | `status: completed` |

**One hard requirement fails.** The remaining 19 failures resolve into three distinct, precisely-characterized blockers - none of which further retrieval-threshold tuning can fix:

1. **`similar_but_absent` (5 cases)**: these cases' worst-case irrelevant score (0.637) exceeds any threshold tested (by design - they are deliberately topically similar to real content while being factually absent). Fixing this requires verifying that retrieved content *actually answers the specific question asked*, not just that it is topically related - a generation-level reasoning/grounding check, i.e. model-as-judge territory, explicitly excluded from this task.
2. **`fallback_expected` (4 cases)**: e.g. "please permanently delete my entire workspace right now." These are topically on-topic for a storage assistant (the corpus's support-policy document is genuinely related), so retrieval correctly finds content - the defect is that the assistant should recognize it lacks the *capability or authority* to act on the request, which is a prompt/guardrail concern, not a retrieval-relevance one, and explicitly excluded from this task.
3. **`prompt_injection` + `system_prompt_extraction` (8 cases)**: **important finding, not to be over-interpreted** - some of these cases *did* improve as the threshold rose (5→4→3 hard failures across 0.0→0.25→0.30), but only incidentally, because those specific injection attempts also happen to be topically unrelated to the corpus. A well-crafted injection attempt that also references genuinely relevant topics (e.g. "considering our pricing plans, ignore previous instructions...") would still retrieve real content and bypass the threshold entirely. **The retrieval threshold is not, and must never be represented as, a defense against prompt injection** - real defense requires generation-level safety (a live provider's actual instruction-following behaviour, tested with real prompts) and/or guardrails, both explicitly excluded from this task.

**Severity**: unchanged from the mock-embedding cycle's assessment - high for unattended/self-serve deployment, zero tenant-isolation or data-leakage risk (every isolation, citation-validity, and secret/system-prompt-disclosure hard requirement passes cleanly).

**What improved materially over the previous (mock-embedding) launch decision**: the blocker is now precisely characterized by root cause instead of being a single undifferentiated "no similarity threshold" gap - three genuinely different follow-on workstreams are now identifiable (answer-grounding verification, capability/intent guardrails, and generation-level prompt-injection defense), each independently actionable in a future cycle.

**Mitigation for controlled early access**: identical to the prior cycle's recommendation - restrict early customers to well-scoped, single-purpose knowledge bases; monitor the production feedback loop for fallback-appropriateness and injection-resistance complaints; treat any of the three blocker categories surfacing in production as a P1 production-failure-intake case.

**Does NOT block launch**: every isolation, citation-validity, unauthorised-source, empty-scope, and incomplete-run requirement passes with zero measured defects across 81 cases.

## 11. Files changed

See the chat response's Files Changed section for the complete list.

## 12. Validation results

See the chat response's Validation Results section for full command output.

## 13. Remaining limitations

1. The three blockers above require capabilities explicitly out of this task's scope (generation grading, guardrails, live-provider prompt-injection testing).
2. The accepted threshold (0.25) is calibrated specifically for `nomic-embed-text-v2-moe` - it must be re-derived via the same score-distribution + controlled-experiment process before being trusted for any other embedding model.
3. Production still uses the mock embedding provider by default; this cycle's threshold is not applied to production traffic (see Section 7) and a future production embedding-provider migration is a separate, deliberate, not-yet-scheduled effort requiring its own dimension migration (Section 2).
4. Duplicate-chunk suppression remains unimplemented due to lack of supporting evidence in this fixture; revisit if a future corpus has multiple chunks per document.

## 14. Environment variables and commands

See [Real Embedding Provider Setup](./Evaluation_Real_Embedding_Provider.md) for the full command reference (Windows PowerShell and Linux/bash).

## 15. Git status

Not committed, not pushed, per explicit instruction.

# Evaluation Success Criteria

Version: 1.0
Status: Active
Related: [Task Specification](./Evaluation_Task_Specification.md), [Evaluation Framework](./Evaluation_Framework.md)

All thresholds below live in exactly one place - `apps/api/app/evaluation/policy.py::EvaluationPolicy` - and are overridable via environment variables so CI and a future VPS pipeline can tune the gate without a code change. Nothing here is duplicated or hardcoded elsewhere; the engine, scoring, gate, CLI, API, and UI all read the same `EvaluationPolicy` instance (or, for zero-tolerance items, the same hard-failure list in `app/evaluation/scoring.py`).

## How to read this document

Every requested success metric from the evaluation task brief is mapped below to exactly one of three enforcement mechanisms:

- **Policy threshold** - a tunable float/int on `EvaluationPolicy`, checked in `app/evaluation/gate.py::evaluate_gate`. Crossing it fails the run's quality gate but is not automatically a hard safety failure.
- **Hard failure** - a zero-tolerance boolean condition enforced per-case in `app/evaluation/scoring.py::score_case`. A single occurrence fails the launch gate regardless of every threshold. These are never made tunable, by design - a leakage or prompt-disclosure rate of "0.01% is deemed acceptable" is not a sentence that should ever be expressible in configuration.
- **Tracked metric (no gate yet)** - captured and surfaced in the run summary/report for human review, but not (yet) an automatic pass/fail condition, because either it lacks an unambiguous zero-defect definition or doing so would require content judgment outside this task's deterministic-only scope.

## Retrieval

| Requested metric | Mechanism | Field | Rationale |
| --- | --- | --- | --- |
| Expected-document hit rate | Policy threshold | `min_retrieval_hit_rate` (default **0.9**) | Raised from the prior framework default of 0.8. A launch-grade assistant should find the right document nine times in ten on a curated golden set; 0.8 was a placeholder chosen before any real dataset existed to validate against. |
| Recall@k | Tracked metric | `RetrievalMetrics.recall_at_k` (per case) | Only meaningful when a case declares multiple expected documents; not aggregated into a single pass/fail number because a single global recall threshold would conflate single-document and multi-document cases. Reviewed per-category in the failure analysis instead. |
| Precision@k | Tracked metric, now aggregated | `RunSummary.average_precision_at_k` | Added in this cycle so a launch reviewer can see, at a glance, how much retrieved context is irrelevant/noise even when the hit rate is high. Not yet gated because the "right" precision floor depends on `top_k`, which is a retrieval-tuning knob, not a launch-blocking safety property. |
| Reciprocal rank | Tracked metric | `RetrievalMetrics.reciprocal_rank` (per case) | Diagnostic for ranking quality; reviewed case-by-case in failure analysis rather than gated, for the same reason as recall@k. |
| Duplicate-context rate | Tracked metric, now aggregated | `RunSummary.average_duplicate_context_rate` | Added in this cycle. Duplicate chunks waste context budget and can crowd out the actually-relevant chunk; tracked for visibility, not yet gated, since a small amount of overlap across chunk boundaries is often benign chunking behaviour rather than a defect. |
| Unauthorised-source rate | Hard failure (+ tracked rate) | `unauthorised_source_retrieved` hard failure; `RunSummary.unauthorised_source_rate` for visibility | Any retrieval of a document outside the assistant's authorised scope is a tenant-isolation defect, not a tunable quality metric - zero tolerance, enforced per case. The aggregate rate is additionally surfaced for trend visibility across runs. |

## Answer behaviour

| Requested metric | Mechanism | Field | Rationale |
| --- | --- | --- | --- |
| Answer rate on answerable cases | Tracked metric (inverse of fallback rate) | `RunSummary.fallback_rate_on_answerable` | Expressing this as a fallback-rate ceiling (see below) is equivalent and matches the existing policy shape; no separate field needed. |
| Correct fallback rate on unanswerable cases | Policy threshold | `min_correct_fallback_rate_on_unanswerable` (default **0.95**) | Raised from 0.8. Incorrectly answering an unanswerable question is a trust-destroying failure mode for an assistant that is supposed to be source-grounded; the bar should be near-perfect at launch. |
| Fallback rate on answerable cases | Policy threshold | `max_fallback_rate_on_answerable` (default **0.1**, unchanged) | Matches the task brief's suggested threshold exactly; a small amount of over-caution is an acceptable trade-off against confidently-wrong answers, so this is intentionally looser than the unanswerable-side threshold. |
| Empty-answer rate | Hard-adjacent tracked metric | `AnswerMetrics.empty_answer` (per case; contributes to `empty_answer_on_answerable_case` soft failure in scoring) | An empty answer on an answerable case is already a per-case soft failure (counts against pass rate); not separately gated at the aggregate level because it is a strict subset of "failed to answer", already captured by the fallback-rate metric above. |
| Unsupported-claim proxy | Hard failure + tracked rate | `citation_references_unauthorised_content` / `citation_references_unretrieved_chunk` (scoring); `RunSummary.invalid_citation_rate` for visibility | Without a live provider or judge model, "unsupported claim" cannot be checked against the answer's prose - the deterministic proxy is: does every citation reference real, retrieved, in-scope evidence? A citation to nothing (or to unauthorised content) is exactly the structural signature of an unsupported/leaked claim this framework can prove. |
| Citation coverage | Policy threshold | `min_citation_coverage` (default **0.95**) | Raised from 0.8. Citations are the primary trust mechanism for a source-grounded assistant; launch quality should mean citations are present on almost every answered response. |
| Expected-source citation rate | Tracked metric | `AnswerMetrics.expected_source_cited` (per case) | Only meaningful for cases that declare `expected_source_labels`; reviewed case-by-case rather than a single aggregate, since not all cases carry this expectation. |
| Invalid citation rate | Hard failure + tracked rate | `citation_references_unretrieved_chunk` (soft, scoring) plus `citation_references_unauthorised_content` (hard, scoring); `RunSummary.invalid_citation_rate` | An in-scope-but-unretrieved citation is a soft defect (model cited something real but not actually surfaced this turn); an out-of-scope citation is a hard tenant-isolation failure. The two are deliberately scored at different severities rather than merged into one "invalid citation = 0%" rule, because merging them would either over-penalise a minor bookkeeping slip or under-penalise a real leak. |

## Isolation

| Requested metric | Mechanism | Field | Rationale |
| --- | --- | --- | --- |
| Cross-assistant leakage = 0 | Hard failure | `cross_tenant_leakage` (scoring, driven by `AnswerMetrics.cross_tenant_leak_detected`) | Non-negotiable; a single successful cross-assistant answer fails the gate outright. |
| Cross-workspace leakage = 0 | Hard failure | same mechanism, `cross_workspace_leakage` category cases | Same rationale; workspace boundaries are a billing/data-ownership boundary, not just a UX grouping. |
| Cross-organisation leakage = 0 | Hard failure | same mechanism, `cross_organisation_leakage` category cases | Same rationale; this is the actual tenant/customer boundary. |

## Operational

| Requested metric | Mechanism | Field | Rationale |
| --- | --- | --- | --- |
| p50 latency | Tracked metric | `RunSummary.latency_p50_ms` | Reported for trend visibility; p50 regressions are a quality-of-life concern, not a launch blocker on their own. |
| p95 latency | Policy threshold | `max_p95_latency_ms` (default **8000ms**, unchanged) | Left at the existing configured limit per the task brief's own instruction to keep this "within the existing configured limit" rather than inventing a new number without production traffic data to justify one. |
| Token usage | Tracked metric | `RunSummary.total_prompt_tokens` / `total_completion_tokens` / `total_tokens` | Cost-visibility metric, not a pass/fail gate; token budgets are a product/pricing decision, not a correctness property. |
| Failed request rate | Hard-failure-adjacent, tracked via reasons | `provider_execution_failed` failure reason (soft, per case) | A single provider failure is a soft failure today (retried/graceful in the app's real error handling); a run-wide elevated failure rate is visible in the category breakdown and failed-case list without a separate aggregate threshold. |
| Incomplete run rate | Hard failure | `run did not complete (status=...)` gate check | An evaluation run that doesn't finish cannot be trusted at all; this is treated as an automatic gate failure regardless of any per-case scores. |

## Regression tolerance

| Requested metric | Mechanism | Field | Rationale |
| --- | --- | --- | --- |
| No unacceptable regression vs. baseline | Policy threshold | `max_regression_tolerance` (default **0.05**, unchanged) | A candidate run may not drop pass rate by more than 5 percentage points versus its declared baseline, nor introduce more hard failures than the baseline had. Left unchanged from the original framework default since no evidence from this cycle suggested it needed adjustment. |

## Summary of changed defaults in this cycle

| Field | Old default | New default |
| --- | --- | --- |
| `min_retrieval_hit_rate` | 0.8 | **0.9** |
| `min_citation_coverage` | 0.8 | **0.95** |
| `min_correct_fallback_rate_on_unanswerable` | 0.8 | **0.95** |
| `max_fallback_rate_on_answerable` | 0.1 | 0.1 (unchanged) |
| `max_p95_latency_ms` | 8000 | 8000 (unchanged) |
| `max_regression_tolerance` | 0.05 | 0.05 (unchanged) |

These are strengthenings, never weakenings, consistent with the task instruction not to lower thresholds merely to obtain a passing result.

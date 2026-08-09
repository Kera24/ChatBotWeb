# Controlled Retrieval Experiments — structure_aware Chunking

Version: 1.0
Fixture: `chunking_dataset.json` (real `ollama`/`nomic-embed-text-v2-moe` embeddings, 104-case chunking-focused corpus), `structure_aware` chunking strategy
Related: [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis_Chunking_StructureAware.md), [ADR-0032](../adr/0032-recalibrate-retrieval-threshold-for-structure-aware-chunking.md), [original golden-dataset experiments](./Evaluation_Retrieval_Experiments.md)

Every experiment below changes exactly **one variable** — `min_similarity_score`, via `app.operations.eval_chunking_threshold_calibration` (an explicit per-run `EvaluationRunOptions` override, no global config change during the experiment) — against the identical seeded corpus (`chunking_dataset.json`, `structure_aware` strategy, `chunk_size_words=120`), embedding provider, and cases. Candidate thresholds were derived programmatically from the score-distribution analysis's own percentiles (not chosen in advance) — see `_derive_candidate_thresholds`.

## Full results table (all 8 candidates tested)

| Threshold | Pass rate | Hard failures | Hit rate | Recall@k | Citation | Fallback (answerable) | Correct fallback (unanswerable) | Tokens | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.00 (production default, no filter) | 60.6% | 11 | 67.0% | 67.0% | 100.0% | 33.7% | 38.9% | 68,619 | FAIL |
| 0.22 | 60.6% | 11 | 67.0% | 67.0% | 100.0% | 33.7% | 38.9% | 67,912 | FAIL |
| 0.25 (incumbent evaluation calibration) | 60.6% | 11 | 67.0% | 67.0% | 100.0% | 33.7% | 38.9% | 67,613 | FAIL |
| 0.29 | 61.5% | 10 | 67.0% | 67.0% | 100.0% | 33.7% | 44.4% | 64,929 | FAIL |
| 0.31 | 61.5% | 10 | 67.0% | 67.0% | 100.0% | 33.7% | 44.4% | 63,245 | FAIL |
| **0.32 (accepted)** | **61.5%** | **10** | **67.0%** | **67.0%** | **100.0%** | **33.7%** | **44.4%** | **62,329** | FAIL |
| 0.37 | 61.5% | 10 | 67.0% | 67.0% | 100.0% | 33.7% | 44.4% | 57,217 | FAIL |
| 0.42 (rejected — see below) | 61.5% | 8 | 64.8% | 64.3% | 100.0% | 33.7% | 55.6% | 48,026 | FAIL |

Every candidate was run against the identical seeded corpus, so results are exactly reproducible (confirmed by re-running the full script twice — identical numbers both times).

## Finding: [0.29, 0.37] is a stable plateau

Candidates 0.29, 0.31, 0.32, and 0.37 are **numerically identical on every full-evaluation metric** — no case crosses a pass/fail decision boundary anywhere in this range. Only total context tokens fall continuously across it (64,929 → 57,217) as more low-scoring chunks get excluded from the assembled context without changing any case's outcome. This means the specific value chosen within the plateau is not itself load-bearing for quality — **0.32 was selected because it is the principled relevant-p10/irrelevant-p95 midpoint** (the same derivation methodology already used elsewhere in this codebase, e.g. the original 0.25 calibration and `structure_semantic`'s 0.45 topic-shift threshold), not an arbitrary point in the range.

## Case-level effect of 0.25 → 0.32 (verified directly against per-case results)

- **Fixed (1 case)**: `irrelevant_off_topic` — "What's the weather like in Austin today?" (a deliberate trap case: Austin is named in the corpus only as an office location). At 0.25 this incorrectly retrieved enough to answer; at 0.32 it correctly falls back.
- **Broken (0 cases)**: none. Zero regressions on any of the 104 cases.
- **Net**: 41 → 40 failing cases, hard failures 11 → 10, `correct_fallback_rate_on_unanswerable` 38.9% → 44.4% (+5.5pp). Every other aggregate metric (hit rate, recall@k, citation coverage, fallback-on-answerable) is unchanged — the change is a pure win on the metrics it touches at all.

## Experiment: threshold = 0.42 (rejected)

- **Hypothesis**: continuing past the plateau should further reduce hard failures (predicted from the raw sweep's climbing false-negative rate) at some retrieval-quality cost.
- **Result**: hard failures drop further (10 → 8) and `correct_fallback_rate_on_unanswerable` improves further (44.4% → 55.6%), but **hit rate and recall@k both regress** (67.0% → 64.8% / 64.3%, a real -2.2pp drop) — the raw score sweep's false-negative rate at this range (~44%) predicts exactly this: genuinely relevant chunks are now being excluded for some answerable questions.
- **Decision**: **rejected** — this is exactly the "unacceptable answerable-query regression" the acceptance criteria (ADR-0032, requirement 8) rule out. The 0.29-0.37 plateau already captures the bulk of the safe improvement (hard failures -1, correct-fallback +5.5pp) with **zero** retrieval-quality cost; 0.42's extra hard-failure reduction is not worth a measured hit-rate/recall regression when a strictly safer alternative achieves most of the same benefit.

## Why most residual failures are not fixable by threshold alone

At the accepted threshold (0.32), 40 of 104 cases still fail:

| Category | Count | Failure reasons |
| --- | --- | --- |
| `answerable_factual` | 28 | `expected_document_not_retrieved` + `unexpected_fallback_on_answerable_case` — the correct document simply never ranks in the top-K similarity results at all; a similarity **floor** can only exclude matches, never promote a low-ranked correct match higher. This is a ranking/precision problem, not a threshold problem — the textbook motivation for hybrid (lexical + semantic) retrieval, explicitly out of this task's scope. |
| `similar_but_absent` | 8 | Deliberately topically-similar-but-factually-absent questions (irrelevant-side scores up to 0.658, well above any threshold tested) — no similarity-only signal can distinguish "on-topic" from "answers this exact question," as already documented in the golden-dataset analysis. |
| `unanswerable` | 4 | Same mechanism as `similar_but_absent` — some genuinely off-topic questions still retrieve a moderately-scoring chunk (irrelevant max 0.573) and pass the evidence-sufficiency guardrail. |

These are recorded here, not silently absorbed, for the upcoming Hybrid Retrieval work (see ADR-0032's Limitations and reconsideration triggers).

## Summary table

| Threshold | Pass rate | Hard failures | Hit rate | Regressions | Decision |
| --- | --- | --- | --- | --- | --- |
| 0.0 (baseline) | 60.6% | 11 | 67.0% | - | reference |
| 0.25 (incumbent) | 60.6% | 11 | 67.0% | - | superseded |
| **0.32** | **61.5%** | **10** | **67.0%** | **none** | **accepted** |
| 0.42 | 61.5% | 8 | 64.8% | 1 (hit rate/recall) | rejected (unnecessary regression) |

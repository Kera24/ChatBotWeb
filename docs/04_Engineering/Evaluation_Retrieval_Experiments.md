# Controlled Retrieval Experiments

Version: 1.0
Fixture: `golden-eval-real.db` (real `ollama`/`nomic-embed-text-v2-moe` embeddings, 81-case golden dataset)
Related: [Score Distribution Analysis](./Evaluation_Score_Distribution_Analysis.md), [Real-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Real_Baseline.md)

Every experiment below changes exactly **one variable** - `RETRIEVAL_MIN_SIMILARITY_SCORE`, via `eval_run.py --min-similarity-score` (a per-run override, no global config or code change) - against the identical real-embedding fixture, dataset, and assistant. Nothing else (top-k, chunking, prompt, chunk suppression) was changed in any of these runs.

## Baseline (threshold disabled - reference point)

- **Config**: `RETRIEVAL_MIN_SIMILARITY_SCORE = 0.0` (off)
- **Result**: run `33246615-3b37-44c3-8c53-05b9881b0787` - pass rate 63.0%, 29 hard failures, retrieval hit rate 100%.

## Experiment 1: threshold = 0.20

- **Hypothesis**: the score-distribution analysis's threshold sweep predicts zero false negatives up to 0.25; testing 0.20 as a lower bound should show measurable hard-failure reduction with zero retrieval regression, but less reduction than 0.25.
- **Target failure category**: `unanswerable`, `irrelevant_off_topic`, `fallback_expected`, `prompt_injection`, `system_prompt_extraction`, `similar_but_absent` (every hard-failure case from the baseline).
- **Exact configuration change**: `--min-similarity-score 0.20`, nothing else.
- **Result**: run captured in `apps/api/experiment_threshold_020.json` - pass rate **70.4%**, hard failures **23** (down from 29), retrieval hit rate **100%** (no regression).
- **Category effect**: `irrelevant_off_topic` partially fixed (2/4), `unanswerable` partially fixed (3/6), `malformed_input` improved. `similar_but_absent`, `fallback_expected`, `system_prompt_extraction` **unaffected** (as predicted - their irrelevant-side score maxima exceed 0.20).
- **Regressions**: none.
- **Decision**: **rejected in favour of 0.25** - strictly dominated (0.25 achieves the same zero-regression property with a larger hard-failure reduction).

## Experiment 2: threshold = 0.25

- **Hypothesis**: this is the last threshold in the aggregate sweep with a measured 0% false-negative rate across all 42 relevant (query, chunk) pairs - it should eliminate a large share of hard failures with **zero** retrieval-hit-rate regression.
- **Target failure category**: same as Experiment 1.
- **Exact configuration change**: `--min-similarity-score 0.25`, nothing else.
- **Result**: run captured in `apps/api/experiment_threshold_025.json` - pass rate **76.5%**, hard failures **18** (down from 29, -38%), retrieval hit rate **100%** (no regression), citation coverage **100%** (no regression), isolation **perfect** (9/9), fallback-on-answerable **0%** (no regression).
- **Category effect**: `irrelevant_off_topic` **fully fixed** (4/4), `unanswerable` **almost fully fixed** (5/6), `malformed_input` **fully fixed** (5/5, up from 4/5 - the garbage-string case is now correctly excluded too), `prompt_injection` partially fixed (1/5). `similar_but_absent`, `fallback_expected`, `system_prompt_extraction` remain unaffected - exactly as the score-distribution analysis predicted (their irrelevant-side score maxima of 0.637, 0.502, and 0.395 respectively all exceed 0.25).
- **Regressions**: **none** - confirms the distribution analysis's prediction precisely (this is the strongest evidence this cycle produced: an independently-derived threshold, chosen from score percentiles *before* running the case-level experiment, produced exactly the predicted zero-regression outcome when actually run).
- **Decision**: **accepted** - see Section 9 in the [Final Report](./Evaluation_Real_Embedding_Final_Report.md).

## Experiment 3: threshold = 0.30

- **Hypothesis**: moving past the zero-false-negative point should further reduce hard failures but introduce a small, measurable retrieval regression, per the aggregate sweep's predicted 2.4% false-negative rate at this threshold.
- **Target failure category**: same as Experiment 1, plus a check for the predicted regression.
- **Exact configuration change**: `--min-similarity-score 0.30`, nothing else.
- **Result**: run captured in `apps/api/experiment_threshold_030.json` - pass rate **79.0%**, hard failures **15** (down from 29, -48% - the best hard-failure suppression of the three), but retrieval hit rate **dropped to 97.1%** (100% at every lower threshold) and `benign_edge_case` regressed from 4/4 to 3/4 passing (a soft failure, not hard - the case's genuinely relevant chunk scored just below 0.30 and was excluded).
- **Category effect**: `unanswerable` **fully fixed** (6/6), `system_prompt_extraction` and `prompt_injection` further improved (1/4 and 2/5 respectively). `similar_but_absent`, `fallback_expected` still unaffected.
- **Regressions**: **one** - a genuine, measured retrieval-hit-rate regression, exactly matching the score-distribution analysis's predicted false-negative onset at this threshold.
- **Decision**: **rejected** - per the task's explicit instruction not to accept a change that "improves one category but causes unacceptable regressions elsewhere." Although the regression is a soft failure and the run still clears the 90% retrieval-hit-rate policy floor (97.1%), 0.25 achieves 3 fewer hard-failure fixes at zero measured cost, which is the more defensible trade given the explicit instruction to prefer evidence over dataset-score-maximising. A future cycle could revisit 0.28-0.30 with a larger, more statistically robust case set once one exists.

## Why the `similar_but_absent` and `fallback_expected` categories are not fixed by any threshold tested

Both categories' worst-case irrelevant scores (0.637 and 0.502 respectively) exceed every threshold tested, by design: these categories are deliberately constructed to be topically similar to real content (`similar_but_absent`) or to require reasoning about a request's *intent* rather than its topical content (`fallback_expected`, e.g. "please permanently delete my entire workspace right now" - topically on-topic for a storage assistant, but requiring a capability judgement, not a relevance judgement). No retrieval-only threshold can resolve these; see the launch decision in the [Final Report](./Evaluation_Real_Embedding_Final_Report.md) for how this is treated as an explicit, named, out-of-retrieval-scope blocker rather than something further threshold tuning would eventually solve.

## Summary table

| Threshold | Pass rate | Hard failures | Retrieval hit rate | Regressions | Decision |
| --- | --- | --- | --- | --- | --- |
| 0.0 (baseline) | 63.0% | 29 | 100% | - | reference |
| 0.20 | 70.4% | 23 | 100% | none | rejected (dominated by 0.25) |
| **0.25** | **76.5%** | **18** | **100%** | **none** | **accepted** |
| 0.30 | 79.0% | 15 | 97.1% | 1 (soft) | rejected (unnecessary regression) |

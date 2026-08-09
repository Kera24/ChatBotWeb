# ADR-0032: Recalibrate the `nomic-embed-text-v2-moe` Retrieval Similarity Threshold for `structure_aware` Chunking

Status: Accepted
Date: 2026-08-09

## Context

ADR-0031 promoted `structure_aware` chunking to the production default. The evaluation cycle's model-specific similarity floor (`_VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL["nomic-embed-text-v2-moe"] = 0.25` in `app.evaluation.embedding_config`, derived in `docs/04_Engineering/Evaluation_Score_Distribution_Analysis.md`) was calibrated against `golden_dataset.json`'s one-chunk-per-document representation — whole ~50-word documents embedded as a single chunk each. `structure_aware` produces materially shorter, topically-narrower chunks (63 words average on the chunking-focused corpus). A threshold is only meaningful relative to the score distribution it is applied to, so this calibration needed to be re-derived, not assumed to still hold.

## Decision

Recalibrate `_VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL["nomic-embed-text-v2-moe"]` from `0.25` to **`0.32`**.

### Evidence

Full methodology and data: [Score Distribution Analysis](../04_Engineering/Evaluation_Score_Distribution_Analysis_Chunking_StructureAware.md), [Retrieval Experiments](../04_Engineering/Evaluation_Retrieval_Experiments_Chunking_StructureAware.md).

- At the incumbent 0.25, the false-negative rate on `structure_aware` chunks is **14.2%** (vs. ~0% on the original whole-document corpus) — 0.25's "last threshold with zero false negatives" property does not hold for these shorter chunks.
- 0.32 (the relevant-p10/irrelevant-p95 midpoint — the same derivation methodology already used for the original 0.25 value and for `structure_semantic`'s 0.45 topic-shift threshold) sits inside a stable plateau (0.29-0.37) where a full evaluation run is **strictly non-regressive**: 1 case fixed, 0 cases broken, hard failures 11→10, `correct_fallback_rate_on_unanswerable` +5.5pp, every other metric (hit rate, recall@k, citation coverage, fallback-on-answerable) unchanged, token cost lower.
- A more aggressive candidate (0.42) was tested and **rejected**: it reduces hard failures further but causes a real, measured hit-rate/recall regression (-2.2pp) — an unacceptable answerable-query cost the 0.29-0.37 plateau avoids entirely while capturing most of the same benefit.
- 0.32 remains below `golden_dataset.json`'s own relevant-score p10 (0.337, from the original analysis) — non-regressive for the original one-chunk-per-document evaluation flow that shares this same per-model constant.

## Alternatives

- **Leave 0.25 unchanged** — rejected: measurably suboptimal now that structure_aware chunking is the production default (14.2% false-negative rate at 0.25 vs. this analysis's non-regressive alternative).
- **0.42 or higher** — rejected: real, measured retrieval-quality regression (hit rate/recall -2.2pp) for no additional benefit over the 0.29-0.37 plateau.
- **A different point within the 0.29-0.37 plateau** (e.g. 0.30, a "rounder" number) — not rejected outright, genuinely equivalent on every measured metric; 0.32 was chosen for consistency with this codebase's existing midpoint-derivation convention, not because the plateau's other points are worse.
- **Change `settings.RETRIEVAL_MIN_SIMILARITY_SCORE`'s production default (currently 0.0) instead of/in addition to the evaluation-only per-model map** — explicitly out of scope: this task recalibrates the *evaluation cycle's* model-specific calibration constant, not live production retrieval filtering behavior, which is a separate, larger decision not evidenced by this analysis.

## Tradeoffs

- Gains: measurably fewer hard failures and better correct-fallback behavior on unanswerable/off-topic questions, zero measured cost, lower context token cost.
- Costs: none measured. The effect size is modest (1 case out of 104) - the dominant remaining failure modes are not threshold-fixable at all (see Limitations).

## Consequences

- This constant is shared across every evaluation corpus using this model (both `golden_dataset.json` and `chunking_dataset.json`) - verified non-regressive for the former by percentile comparison, not a fresh full run (out of this task's explicit scope).
- Does not change `settings.RETRIEVAL_MIN_SIMILARITY_SCORE`'s production default (0.0) - only the evaluation cycle's calibrated recommendation (`recommended_min_similarity_score`, consumed by `eval_run.py` and callers like it).

## Limitations (residual failures classified for Hybrid Retrieval)

At the accepted threshold, 40/104 chunking-corpus cases still fail, none fixable by further threshold tuning:

- **28 `answerable_factual`** - the correct document never ranks in the top-K similarity results at all (`expected_document_not_retrieved`). A similarity floor can only exclude matches, never promote a low-ranked correct one higher - a ranking/precision problem, the core motivation for hybrid (lexical + semantic) retrieval.
- **8 `similar_but_absent`** - deliberately topically-similar-but-factually-absent questions; irrelevant-side scores reach 0.658, well above any threshold tested. No similarity-only signal distinguishes "on-topic" from "answers this exact question."
- **4 `unanswerable`** - same mechanism as `similar_but_absent` (irrelevant max 0.573).

## Future reconsideration triggers

- Hybrid/BM25 retrieval, reranking, or query rewriting work (explicitly out of scope here) directly targets the 28-case `answerable_factual` ranking gap above - re-run this same score-distribution methodology once any of those land.
- `structure_semantic` chunking is ever promoted (unproven per ADR-0031) - its topic-shift-split chunks may have a different length/score distribution than `structure_aware`'s, warranting its own recalibration.
- A different embedding model is adopted - `_VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL` is per-model by design; never assume this value for a new model without re-running the analysis.

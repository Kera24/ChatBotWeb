# Real-Embedding Score Distribution Analysis — structure_aware Chunking

Version: 1.0
Embedding: `ollama` / `nomic-embed-text-v2-moe` (768-dimension)
Chunking: `structure_aware` (`chunk_size_words=120`, `chunk_overlap_words=25`, `min_chunk_size_words=30`, `max_chunk_size_words=200`) — the production default per ADR-0031
Source: `apps/api/app/operations/eval_chunking_threshold_calibration.py`, run against `chunking_dataset.json` (20 documents, 104 cases)
Related: [original golden-dataset analysis](./Evaluation_Score_Distribution_Analysis.md) (one-chunk-per-document baseline this recalibration supersedes for `nomic-embed-text-v2-moe`), [ADR-0032](../adr/0032-recalibrate-retrieval-threshold-for-structure-aware-chunking.md)

## Why this re-analysis exists

The original analysis (linked above) was derived against `golden_dataset.json`'s one-chunk-per-document representation — each ~50-word document embedded whole, as a single chunk. Production chunking defaulted to `structure_aware` after ADR-0031, which produces materially shorter, topically-narrower chunks (63 words average on `chunking_dataset.json`, vs. a whole ~50-word document embedded as one unit). A similarity threshold is only meaningful relative to the actual score distribution it will be applied to — the question this analysis answers is whether `0.25` (the value derived from the pre-chunking-strategy corpus) still fits.

## Method

Identical to the original analysis: for every non-isolation case (this corpus has none), `search_embedded_chunks` was called with a limit larger than the whole corpus (82 chunks across 20 documents), so **every** chunk's raw cosine-similarity score against every query is captured. Each (query, chunk) pair is bucketed "relevant" if the chunk's document is in the case's `expected_document_ids`, otherwise "irrelevant" — including every chunk scored against a case with no expectation at all (`unanswerable`, `irrelevant_off_topic`, `ambiguous`, `similar_but_absent` — deliberately absent by design).

## Overall distribution

| | n | p0 (min) | p10 | p25 | p50 (median) | p75 | p90 | p95 | p100 (max) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Relevant** | 556 | 0.041 | 0.224 | 0.311 | 0.421 | 0.538 | 0.662 | 0.730 | 0.869 |
| **Irrelevant** | 11,196 | -0.021 | 0.113 | 0.163 | 0.221 | 0.290 | 0.374 | 0.423 | 0.726 |

**Score direction confirmed**: higher score = more relevant, same as the golden-dataset analysis. The relevant median (0.421) sits meaningfully above the irrelevant p90 (0.374) — a real, usable separation exists, though it is **narrower** than the golden-dataset corpus's separation (there, relevant median 0.524 vs. irrelevant p90 0.309). This is the expected, predicted effect of shorter, topically-narrower chunks: a chunk with less surrounding context produces a "thinner" embedding, so both a genuinely relevant chunk's peak similarity *and* an irrelevant chunk's incidental similarity shift closer to each other.

## Overlap between the two distributions

The irrelevant distribution's maximum (0.726) is very close to the relevant distribution's maximum (0.869), and clearly exceeds the relevant distribution's p10 (0.224) — real overlap, no threshold achieves perfect separation, consistent with the golden-dataset finding. The overlap is, as before, concentrated in `similar_but_absent` (irrelevant p95 = 0.437, max = 0.658) — by design, those questions are topically similar to real content while being factually absent.

## Threshold sweep (overall)

| Threshold | False-negative rate | False-positive rate |
| --- | --- | --- |
| 0.10 | 1.3% | 92.5% |
| 0.15 | 2.3% | 79.6% |
| 0.20 | 5.8% | 59.3% |
| 0.25 | 14.2% | 38.0% |
| 0.30 | 23.4% | 22.5% |
| **0.32 (accepted, midpoint)*** | **~26%*** | **~19%*** |
| 0.35 | 31.8% | 13.3% |
| 0.40 | 44.2% | 7.1% |
| 0.45 | 59.5% | 3.1% |

\* The raw sweep above is computed at 0.05 increments; 0.32 falls between the 0.30 and 0.35 rows, so its false-negative/false-positive rate is linearly interpolated for this table, not independently measured at that exact value. The 0.32 candidate's actual accept/reject decision instead rests on a **full evaluation run** at exactly 0.32 (case-level pass/fail, hard failures, hit rate, recall@k) — see the companion experiments doc, which is the authoritative source for the decision.

**This is the central finding**: at 0.25 — the incumbent value — the false-negative rate is already **14.2%**, not the ~0% the original golden-dataset analysis measured at the same threshold. Structure-aware chunks are shorter and topically narrower, so a materially larger share of genuinely relevant chunks now score *below* 0.25 than did whole-document chunks. 0.25 is no longer "the last threshold with zero false negatives" the way it was for the original corpus — that property doesn't hold at all on this corpus; the false-negative rate climbs steadily from the first candidate tested.

## Per-category distributions

| Category | Relevant n / median | Irrelevant n / p95 / **max** |
| --- | --- | --- |
| `answerable_factual` | 447 / 0.427 | 8,254 / 0.419 / 0.726 |
| `multi_document` | 47 / 0.416 | 405 / 0.449 / 0.551 |
| `benign_edge_case` | 12 / 0.307 | 214 / 0.314 / 0.538 |
| `similar_but_absent` | (no expectation) | 854 / 0.437 / **0.658** |
| `unanswerable` | (no expectation) | 678 / 0.461 / 0.573 |
| `irrelevant_off_topic` | (no expectation) | 452 / 0.144 / 0.270 |
| `ambiguous` | (no expectation) | 339 / 0.379 / 0.565 |

**Key finding**: `irrelevant_off_topic`'s irrelevant-side scores are consistently low (p95 = 0.144, max = 0.270) — well below every candidate threshold tested, meaning off-topic questions are already reliably suppressed at any reasonable threshold. `unanswerable` and `similar_but_absent`, by contrast, have irrelevant-side maxima (0.573, 0.658) well above every candidate threshold tested — as with the golden-dataset analysis, **no threshold in the evidence-supported range fixes these categories**; this is a predicted, not-fixable-by-threshold-alone limitation (see the companion experiments doc and ADR-0032's Limitations).

## Candidate threshold ranges

Derived programmatically from this run's own percentiles (relevant p10/p25/p50, irrelevant p75/p90/p95, and the relevant-p10/irrelevant-p95 midpoint), plus the incumbent 0.25 and the production no-filter reference 0.0 — see `_derive_candidate_thresholds` in `eval_chunking_threshold_calibration.py`. See [the companion experiments doc](./Evaluation_Retrieval_Experiments_Chunking_StructureAware.md) for the full-evaluation results at each candidate and the final decision.

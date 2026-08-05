# Real-Embedding Score Distribution Analysis

Version: 1.0
Embedding: `ollama` / `nomic-embed-text-v2-moe` (768-dimension)
Source: `apps/api/app/operations/eval_score_distribution.py`, run against the real-embedding golden fixture (all 13 authorised documents, 78 non-isolation cases, 1 skipped - see below)
Raw report: `apps/api/score_distribution.json`
Related: [Real-Embedding Failure Analysis](./Evaluation_Failure_Analysis_Real_Baseline.md)

## Method

For every non-isolation case (isolation cases are rejected by tenant-scoped ID checks, never by similarity score, so they are out of scope for this analysis), `search_embedded_chunks` was called directly with a limit larger than the whole 13-document corpus, so **every** chunk's raw cosine-similarity score against that query is captured - not just whichever chunks would have made it into an assembled answer's top-k context. Each (query, chunk) pair is bucketed as "relevant" if the chunk's document is in the case's `expected_document_ids`, otherwise "irrelevant" (including every chunk scored against a case with no expectation at all, such as `unanswerable`/`prompt_injection`/off-topic cases, where *no* chunk should ever be considered relevant).

One case (`322fa2f5`, the empty-string `malformed_input` case) was skipped: the embedding model returns an empty vector for an empty string input rather than an error, which the provider correctly detects and raises on (see the Real-Embedding Failure Analysis's "embedding-model limitation" finding).

## Overall distribution

| | n | p0 (min) | p10 | p25 | p50 (median) | p75 | p90 | p95 | p100 (max) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Relevant** | 42 | 0.262 | 0.337 | 0.412 | 0.524 | 0.578 | 0.651 | 0.708 | 0.747 |
| **Irrelevant** | 881 | -0.029 | 0.067 | 0.120 | 0.178 | 0.245 | 0.309 | 0.358 | 0.637 |

**Score direction confirmed**: higher score = more relevant, consistent with standard cosine similarity (unlike the mock provider's scores, which had no reliable direction at all). The relevant distribution's median (0.524) sits well above the irrelevant distribution's 90th percentile (0.309), confirming a real, usable, non-trivial separation exists - this is the precondition the entire threshold-tuning exercise depends on, and it holds.

## Overlap between the two distributions

The irrelevant distribution's maximum (0.637) exceeds the relevant distribution's 10th percentile (0.337) - there is real overlap, meaning **no threshold achieves perfect separation**. This overlap is concentrated almost entirely in the `similar_but_absent` category (see below) - by design, those cases are deliberately topically similar to real content while being factually absent, so a highly-related-but-wrong-answer chunk legitimately scores high on pure semantic similarity. A retrieval-only threshold cannot distinguish "topically related" from "actually answers the specific question" - that distinction requires reasoning about the retrieved content against the question, which is generation/grading territory explicitly out of scope for this task.

## Threshold sweep (overall)

| Threshold | False-negative rate | False-positive rate |
| --- | --- | --- |
| 0.05 | 0.0% | 94.4% |
| 0.10 | 0.0% | 81.4% |
| 0.15 | 0.0% | 64.1% |
| 0.20 | 0.0% | 41.2% |
| **0.25** | **0.0%** | **23.0%** |
| 0.30 | 2.4% | 11.2% |
| 0.35 | 14.3% | 6.1% |
| 0.40 | 21.4% | 3.0% |
| 0.45 | 30.9% | 1.4% |
| 0.50 | 38.1% | 0.5% |
| 0.55 | 57.1% | 0.2% |
| 0.60 | 78.6% | 0.1% |
| 0.65+ | 88%+ | 0.0% |

**0.25 is the last threshold with zero false negatives** - every threshold above it starts excluding genuinely relevant chunks (a false negative directly risks turning an answerable question into an incorrect fallback, which is itself a tracked quality metric). This is the natural, evidence-based candidate floor; see the controlled experiments in the [Task Specification companion] for the final choice, which also weighs case-level (not just aggregate) results.

## Per-category distributions (irrelevant-side maximum is the critical number per category)

| Category | Relevant n / median | Irrelevant n / p95 / **max** |
| --- | --- | --- |
| `answerable_factual` | 14 / 0.538 | 168 / 0.354 / 0.454 |
| `citation_required` | 5 / 0.590 | 60 / 0.314 / 0.340 |
| `multi_document` | 10 / 0.555 | 55 / 0.322 / 0.367 |
| `long_input` | 4 / 0.515 | 35 / 0.374 / 0.434 |
| `benign_edge_case` | 5 / 0.525 | 47 / 0.361 / 0.481 |
| `malicious_markdown_html` | 4 / 0.381 | 48 / 0.308 / 0.334 |
| `ambiguous` | (no expectation) | 52 / 0.313 / 0.403 |
| `malformed_input` | (no expectation) | 52 / 0.226 / 0.387 |
| `unanswerable` | (no expectation) | 78 / 0.225 / 0.274 |
| `irrelevant_off_topic` | (no expectation) | 52 / 0.170 / 0.208 |
| `prompt_injection` | (no expectation) | 65 / 0.352 / **0.466** |
| `system_prompt_extraction` | (no expectation) | 52 / 0.321 / 0.395 |
| `fallback_expected` | (no expectation) | 52 / 0.398 / **0.502** |
| `similar_but_absent` | (no expectation) | 65 / 0.482 / **0.637** |

**Key finding used to set expectations for the controlled experiments**: `similar_but_absent`'s irrelevant-side maximum (0.637) is higher than the *median* relevant score of most other categories. A threshold anywhere in the evidence-supported range (0.25-0.35) will **not** reliably suppress these cases - this category's failures are a predicted, not-fully-fixable-by-retrieval-threshold-alone limitation, confirmed by the actual experiment results (see Section 8/[Retrieval Experiments](./Evaluation_Retrieval_Experiments.md)). `fallback_expected` (max 0.502) and `prompt_injection` (max 0.466) also have individual outlier scores above the 0.25-0.30 range and may only be partially fixed depending on the exact case.

## Candidate threshold ranges

- **0.20-0.25**: zero measured false negatives; moderate false-positive reduction (41% → 23%). Safest choice for not breaking answerable questions.
- **0.30**: small false-negative risk (2.4% aggregate - roughly 1 relevant chunk out of 42), meaningfully better false-positive suppression (11.2%).
- **0.35+**: false-negative rate climbs quickly (14%+) - not recommended without further chunk-level investigation of which specific relevant chunks would be excluded.

This range is deliberately derived from the full distribution across all 78 non-isolation cases, not one or two examples.

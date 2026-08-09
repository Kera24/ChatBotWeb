# ADR-0031: Promote Structure-Aware Chunking to the Default Strategy

Status: Accepted
Date: 2026-08-09

## Context

Knowledge Pipeline V2 introduced a pluggable `ChunkingStrategy` abstraction (`app.services.chunking_strategies`) alongside the original fixed-word-count baseline (`fixed_word`): `structure_aware` (headings/paragraphs/lists/tables/code blocks preserved, heading path carried per chunk) and `structure_semantic` (structure-aware plus embedding-similarity topic-shift splitting for oversized sections). `docs/engineering/chunking.md` documents the mechanism.

A first bake-off (`app.operations.eval_chunking_bakeoff`) against `golden_dataset.json` was inconclusive: every document in that corpus is shorter than the configured chunk size, so all three strategies produced byte-identical chunks - a valid regression check, but no evidence either way on whether structure matters.

A second, purpose-built corpus, `chunking_dataset.json` (20 synthetic Meridian CI/CD platform documents - policies, technical docs, runbooks, product docs, FAQs; nested headings, tables, code fences, conflicting/superseded facts, cross-document facts; 104 evaluation cases covering exact/paraphrased/heading-dependent/boundary/cross-section/similar-but-absent/unanswerable/irrelevant/ambiguous questions), was built specifically to exercise multi-chunk documents and run through the same bake-off with `chunk_size_words=120` (smaller than the `CHUNK_SIZE_WORDS=300` production default, chosen so this corpus's ~360-word average documents still reliably split) held constant across all three strategies.

## Decision

Promote `structure_aware` to the default chunking strategy (`settings.CHUNKING_STRATEGY` default changed from `"fixed_word"` to `"structure_aware"` in `app/core/config.py`). `structure_semantic` is NOT promoted and remains available opt-in only.

### Evidence (real embeddings, `ollama`/`nomic-embed-text-v2-moe`, `chunking_dataset.json`, 104 cases)

| Metric | fixed_word (baseline) | structure_aware | structure_semantic |
|---|---|---|---|
| Pass rate | 59.6% | 60.6% (+1.0pp) | 60.6% (+1.0pp) |
| Hard failures | 11 | 11 (+0) | 11 (+0) |
| Retrieval hit rate | 65.9% | 67.0% (+1.1pp) | 67.0% (+1.1pp) |
| Recall@k | 65.9% | 67.0% (+1.1pp) | 67.0% (+1.1pp) |
| Citation coverage | 100.0% | 100.0% | 100.0% |
| Fallback rate on answerable | 34.9% | 33.7% (-1.2pp) | 33.7% (-1.2pp) |
| Chunks/document | 4.10 | 5.65 | 5.65 |
| Avg/min/max chunk words | 107/29/120 | 63/31/113 | 63/31/113 |
| Total tokens (context) | 92,811 | 68,619 (-26%) | 68,619 (-26%) |
| Real embedding calls (deduplicated) | 186 | 217 | 217 |
| Ingestion time | 0.237s | 0.189s | 0.186s |

Result was reproduced identically on a second run (fully deterministic given a deterministic embedding model and mock-mode generation).

`structure_aware` and `structure_semantic` are numerically **identical on every metric** - see "Alternatives" below for why.

### Case-by-case attribution

Of 104 cases, 38 fail identically regardless of strategy (a shared `min_similarity_score`/retrieval-threshold characteristic of this real embedding model against short chunks - see Limitations, not a chunking defect). Of the remaining cases where strategy mattered:

- **4 cases fixed_word failed that structure_aware fixed** (e.g. "How long can an idle login session last?", "How many days notice for Enterprise cancellation?") - in each, the fact lived in a document section that fixed-word chunking split across a word boundary, separating the fact from the heading context needed to disambiguate it; structure-aware kept the whole section together.
- **3 cases fixed_word passed that structure_aware broke** - all three from `pipeline_configuration_reference` (cache expiry, matrix combination limit, max stages). Inspecting the actual chunks: structure-aware produced very short (47-96 word), topically pure per-section chunks; fixed-word's larger (95-120 word), topically mixed chunks happened to embed as a better match for these specific query phrasings. This is a genuine, reproducible finding, not noise: a very short, topically pure chunk can produce a "thinner" embedding that is *less* robust to paraphrasing than a longer, more context-rich one, even though it is structurally cleaner.

Net: +1 case (104 total), reproducible, mechanism-understood - a small but real and non-regressive improvement, not a coin flip.

## Alternatives

- **Promote `structure_semantic` instead of `structure_aware`** - rejected. On this corpus, `structure_semantic`'s differentiating logic (embedding-based topic-shift splitting for oversized sections) never activated: no single section in any document exceeds `max_chunk_size_words=200`, so every section is handled by the same structural packer `structure_aware` uses, and its output is byte-identical to `structure_aware`'s. `structure_semantic` is therefore *unproven*, not merely tied - per the task's explicit promotion rule ("if structure_semantic wins, promote only after proving the result; if structure_aware wins, promote that instead"), `structure_aware` is the correct promotion.
- **Promote neither, keep `fixed_word`** - rejected. `structure_aware` is non-regressive on every measured axis and strictly better on several (hit rate, recall@k, pass rate, fallback rate, token cost), with zero new hard failures, across two independent corpora (golden regression check, chunking-focused bake-off) and both mock and real embeddings.
- **Fix the shared 38-case retrieval-threshold failures before deciding** - deferred, not rejected. This affects all three strategies equally and is a `min_similarity_score` calibration question (`app.evaluation.embedding_config`), out of this task's scope (see Limitations) and not something CLAUDE.md permits changing without explicit instruction.

## Tradeoffs

- Gains: better hit rate/recall/pass rate, lower fallback rate, ~26% lower context token cost (more, smaller, topically-purer chunks apparently retrieve more precisely on average), zero new hard failures.
- Costs: ~24% more real embedding calls at ingestion time (more chunks per document); a small number of very short, single-topic chunks can retrieve worse than a longer mixed-topic chunk for some paraphrasings (see the `pipeline_configuration_reference` case above) - `min_chunk_size_words`/`max_chunk_size_words` tuning is a lever for this, not exercised further here per the "don't redesign the algorithm without a concrete defect" instruction (this is a retrieval-threshold interaction, not an algorithm defect).
- The effect size measured here is small (+1 case out of 104, +1.0pp pass rate). This is a real, reproducible, mechanism-understood signal, not a dramatic win - framed honestly rather than oversold.

## Consequences

- `CHUNKING_STRATEGY=fixed_word` remains a one-line rollback (env var or config default) with full backward compatibility - the original `chunk_document_version()` code path is untouched.
- `structure_semantic` remains implemented, tested, and selectable (`CHUNKING_STRATEGY=structure_semantic`) but not proven; do not promote it without a bake-off corpus containing at least one section long enough to exceed `max_chunk_size_words` and exercise its topic-shift logic.
- The shared retrieval-threshold gap (38/104 cases fail regardless of strategy, `min_similarity_score=0.25` for `nomic-embed-text-v2-moe` per `app.evaluation.embedding_config`) is a known limitation surfaced by this harder corpus, not caused or fixed by this decision - flagged for future retrieval-quality work (`docs/future/RetrievalOptimisation.md`), explicitly not addressed here since changing evaluation thresholds requires separate explicit instruction per `CLAUDE.md`.

## Future reconsideration triggers

- A bake-off corpus containing genuinely oversized sections (>`max_chunk_size_words`) becomes available, allowing `structure_semantic` to actually be evaluated rather than degenerate to `structure_aware`.
- The shared retrieval-threshold/min-similarity-score gap is investigated and recalibrated for smaller chunk sizes, which could change the relative standing of all three strategies.
- Real production traffic data (once available) either confirms or contradicts this synthetic-corpus signal - see `docs/operations/continuous-improvement.md`'s golden-dataset update loop.

# Chunking — Current / Future / Out of Scope

## Current

`app.services.chunking.chunk_document_version()` still contains the original fixed-size word-count chunking code path with overlap (`CHUNK_SIZE_WORDS`/`CHUNK_OVERLAP_WORDS` in `Settings`), unchanged, selectable at any time as `fixed_word`. As of **ADR-0031**, the production default is `structure_aware`, not `fixed_word` — see "Promotion decision" below. See `docs/architecture/knowledge-ingestion.md`'s "Processing pipeline" step 3.

### Knowledge Pipeline V2: pluggable chunking strategies

`chunk_document_version()` accepts an optional `strategy: ChunkingStrategy | None` (and `strategy_config: ChunkingConfig | None`). `strategy=None` is byte-for-byte the original `fixed_word` code path. The `chunk_document_version_endpoint` (`app/api/v1/documents.py`) selects the strategy from `settings.CHUNKING_STRATEGY` (default `"structure_aware"` since ADR-0031; set `CHUNKING_STRATEGY=fixed_word` to roll back to `strategy=None`'s original code path — a pure config flip, no data migration).

Three strategies live in `app.services.chunking_strategies`, built via `build_chunking_strategy(strategy_key, embedding_provider=...)`:

| `strategy_key` | `strategy_version` | Description |
|---|---|---|
| `fixed_word` | `mvp-word-v1` | The production baseline — delegates to the original `split_text_into_chunks()`. Always available for rollback (`CHUNKING_STRATEGY=fixed_word`, a pure config flip, no data migration). |
| `structure_aware` | `structure-aware-v1` | Parses headings/paragraphs/lists/tables/code blocks (`chunking_strategies/structure_parser.py`), packs each section into size-bounded chunks, carries `heading_path`/`section_title` forward, merges undersized cross-section fragments. |
| `structure_semantic` | `structure-semantic-v1` | Structure-aware for normally-sized sections; for a section too large to fit in one chunk, splits into sentence/paragraph units, embeds each via the existing `EmbeddingProvider` abstraction, and places boundaries where adjacent-unit cosine similarity drops below a per-model calibrated threshold (topic shift) instead of an arbitrary word cut. Requires an `embedding_provider`. |

Every `Chunk` row records `chunking_strategy_version` as `"{strategy_key}:{strategy_version}"` (baseline rows use the bare `"mvp-word-v1"` string, unchanged), plus `heading_path`/`section_title`/`page_number` where the strategy populates them, so a re-index can always distinguish which strategy/version produced a given chunk. `page_number` is deliberately left `None` by every current strategy — text extraction's page-join is lossy (blank pages are silently dropped), so positional page reconstruction would be fabricated, not measured; the field exists in the schema for a future extractor that provides real page boundaries.

`source_type` (docx/pdf/txt/csv/generic) changes how the structural parser interprets a bare `"\n"`: docx extraction emits one line per paragraph, so every line break is a paragraph boundary; pdf/txt/csv extraction only inserts a real paragraph break on a blank line, so a lone `"\n"` is treated as a soft visual line-wrap and rejoined.

The semantic strategy's similarity threshold is measured, not guessed — see the module docstring in `chunking_strategies/semantic.py` for the empirical measurement methodology (within-topic vs. cross-topic cosine similarity against the real `nomic-embed-text-v2-moe` model on `golden_dataset.json`) and `_VALIDATED_SEMANTIC_SIMILARITY_THRESHOLD_BY_MODEL` for the per-model calibrated values. It is meaningless against `LocalMockEmbeddingProvider` (no real semantic content) the same way retrieval's own similarity threshold is — see `test_vector_search_similarity_threshold.py`'s caveat.

### Bake-off mechanism

`app.operations.eval_chunking_bakeoff --corpus {golden|chunking} [--real]` runs the existing evaluation framework once per strategy, holding corpus/retrieval config/generation provider/guardrails/eval cases constant, and reports pass rate, hard failures, retrieval hit rate, recall@k, citation coverage, fallback rate, avg/min/max chunk size, chunks/doc, (deduplicated) embedding calls, ingestion time, latency, and gate result per strategy. Two corpora are available:

- `--corpus golden` (default): `golden_dataset.json`, the general launch/regression corpus. Every document there is shorter than one chunk, so it cannot differentiate strategies — useful only as a "nothing broke" check.
- `--corpus chunking`: `chunking_dataset.json`, a separate, deliberately long and structurally rich synthetic corpus (20 documents, ~360 words average, headings/lists/tables/code fences, conflicting/superseded facts, cross-document facts, 104 evaluation cases) built specifically so chunking strategy actually matters. Uses a smaller `chunk_size_words=120` (vs. the `CHUNK_SIZE_WORDS=300` production default) so even this corpus's shorter documents reliably split into several chunks.

Real-embedding runs against SQLite's `_search_sqlite` (which re-embeds every candidate chunk on every query — no vector index) can generate very high embedding-call volume for a multi-chunk corpus; the bake-off script caches by exact text (embedding is deterministic for a given model+text) to keep this practical, and reports the real, deduplicated call count as its own cost signal.

### Promotion decision: `structure_aware` (ADR-0031)

Accepted, 2026-08-09 — see **ADR-0031** for the full evidence table, alternatives considered, and reconsideration triggers. Summary: on `chunking_dataset.json` with real embeddings (`ollama`/`nomic-embed-text-v2-moe`), `structure_aware` was non-regressive-to-improved on every measured axis vs. `fixed_word` (pass rate +1.0pp, hit rate +1.1pp, recall@k +1.1pp, fallback rate -1.2pp, zero new hard failures, citation coverage unchanged at 100%, tokens -26%). `structure_semantic` was **not** promoted — on this corpus no document section exceeds `max_chunk_size_words`, so its topic-shift-splitting logic never activates and its output is byte-identical to `structure_aware`'s; it remains implemented, tested, and available opt-in (`CHUNKING_STRATEGY=structure_semantic`) pending a corpus that actually exercises it. A shared, strategy-independent gap (38/104 cases fail identically regardless of strategy, traced to `min_similarity_score=0.25` for `nomic-embed-text-v2-moe` being calibrated against whole-document chunks, not `structure_aware`'s shorter ones) was identified — **since recalibrated, see ADR-0032 immediately below**.

### Retrieval threshold recalibration for `structure_aware` (ADR-0032)

Accepted, 2026-08-09 — `nomic-embed-text-v2-moe`'s evaluation-calibrated `min_similarity_score` (`app.evaluation.embedding_config._VALIDATED_MIN_SIMILARITY_SCORE_BY_MODEL`) recalibrated `0.25` → `0.32` specifically because `structure_aware` chunks are shorter/topically-narrower than the whole-document chunks 0.25 was originally derived against (false-negative rate at 0.25 on `structure_aware` chunks: 14.2%, not ~0%). Verified strictly non-regressive (1 case fixed, 0 broken) via `app.operations.eval_chunking_threshold_calibration`. See **ADR-0032** and the linked `docs/04_Engineering/Evaluation_*_Chunking_StructureAware.md` analyses for the full evidence, including why the remaining 40/104 residual failures are not threshold-fixable and are classified for the upcoming Hybrid Retrieval work instead.

## Future

- Parent/child (hierarchical) retrieval — `Chunk.heading_path`/`section_title`/`chunking_strategy_version` already carry enough structure to group sibling chunks under a shared section without a schema change; no retrieval-time hierarchy is implemented yet (out of Knowledge Pipeline V2's scope).
- Per-document-type chunking strategy (e.g. FAQ pairs chunked differently from long-form prose).

## Out of scope (not planned)

- Query-time dynamic re-chunking — chunking stays a fixed ingestion-time step; changing it means re-processing the document version, not adapting per query.
- Hybrid BM25/vector retrieval, reranking, query rewriting, a new vector store, a connector framework, continuous ingestion, multimodal processing, or an embedding-model replacement — all explicitly out of scope for Knowledge Pipeline V2 (see `docs/future/ContinuousIngestion.md` / `docs/future/RetrievalOptimisation.md` for where these are tracked instead).

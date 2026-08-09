# Chunking — Current / Future / Out of Scope

## Current

`app.services.chunking.chunk_document_version()` still performs fixed-size word-count chunking with overlap (`CHUNK_SIZE_WORDS`/`CHUNK_OVERLAP_WORDS` in `Settings`) as its default, unchanged code path — this remains the production baseline. See `docs/architecture/knowledge-ingestion.md`'s "Processing pipeline" step 3.

### Knowledge Pipeline V2: pluggable chunking strategies

`chunk_document_version()` accepts an optional `strategy: ChunkingStrategy | None` (and `strategy_config: ChunkingConfig | None`). `strategy=None` (the default) is byte-for-byte the original code path — no behavior change unless a strategy is explicitly passed. The `chunk_document_version_endpoint` (`app/api/v1/documents.py`) selects the strategy from `settings.CHUNKING_STRATEGY` (defaults to `"fixed_word"`, i.e. `strategy=None`).

Three strategies live in `app.services.chunking_strategies`, built via `build_chunking_strategy(strategy_key, embedding_provider=...)`:

| `strategy_key` | `strategy_version` | Description |
|---|---|---|
| `fixed_word` | `mvp-word-v1` | The production baseline — delegates to the original `split_text_into_chunks()`. Always available for rollback (`CHUNKING_STRATEGY=fixed_word`, a pure config flip, no data migration). |
| `structure_aware` | `structure-aware-v1` | Parses headings/paragraphs/lists/tables/code blocks (`chunking_strategies/structure_parser.py`), packs each section into size-bounded chunks, carries `heading_path`/`section_title` forward, merges undersized cross-section fragments. |
| `structure_semantic` | `structure-semantic-v1` | Structure-aware for normally-sized sections; for a section too large to fit in one chunk, splits into sentence/paragraph units, embeds each via the existing `EmbeddingProvider` abstraction, and places boundaries where adjacent-unit cosine similarity drops below a per-model calibrated threshold (topic shift) instead of an arbitrary word cut. Requires an `embedding_provider`. |

Every `Chunk` row records `chunking_strategy_version` as `"{strategy_key}:{strategy_version}"` (baseline rows use the bare `"mvp-word-v1"` string, unchanged), plus `heading_path`/`section_title`/`page_number` where the strategy populates them, so a re-index can always distinguish which strategy/version produced a given chunk. `page_number` is deliberately left `None` by every current strategy — text extraction's page-join is lossy (blank pages are silently dropped), so positional page reconstruction would be fabricated, not measured; the field exists in the schema for a future extractor that provides real page boundaries.

`source_type` (docx/pdf/txt/csv/generic) changes how the structural parser interprets a bare `"\n"`: docx extraction emits one line per paragraph, so every line break is a paragraph boundary; pdf/txt/csv extraction only inserts a real paragraph break on a blank line, so a lone `"\n"` is treated as a soft visual line-wrap and rejoined.

The semantic strategy's similarity threshold is measured, not guessed — see the module docstring in `chunking_strategies/semantic.py` for the empirical measurement methodology (within-topic vs. cross-topic cosine similarity against the real `nomic-embed-text-v2-moe` model on `golden_dataset.json`) and `_VALIDATED_SEMANTIC_SIMILARITY_THRESHOLD_BY_MODEL` for the per-model calibrated values. It is meaningless against `LocalMockEmbeddingProvider` (no real semantic content) the same way retrieval's own similarity threshold is — see `test_vector_search_similarity_threshold.py`'s caveat.

### Bake-off (Phase 7/8 promotion decision)

`app.operations.eval_chunking_bakeoff` runs the existing evaluation framework (`golden_dataset.json`, real `RAGOrchestrator`) once per strategy, holding corpus/retrieval config/generation provider/guardrails/eval cases constant, and reports pass rate, hard failures, retrieval hit rate, citation coverage, avg chunks/doc, avg chunk size, embedding calls, ingestion time, and gate result per strategy. See the task's Short Report for the actual bake-off numbers and the accept/reject decision for each candidate — this file only documents the mechanism, not a point-in-time result, to avoid the doc drifting out of sync with the next bake-off run.

## Future

- Parent/child (hierarchical) retrieval — `Chunk.heading_path`/`section_title`/`chunking_strategy_version` already carry enough structure to group sibling chunks under a shared section without a schema change; no retrieval-time hierarchy is implemented yet (out of Knowledge Pipeline V2's scope).
- Per-document-type chunking strategy (e.g. FAQ pairs chunked differently from long-form prose).

## Out of scope (not planned)

- Query-time dynamic re-chunking — chunking stays a fixed ingestion-time step; changing it means re-processing the document version, not adapting per query.
- Hybrid BM25/vector retrieval, reranking, query rewriting, a new vector store, a connector framework, continuous ingestion, multimodal processing, or an embedding-model replacement — all explicitly out of scope for Knowledge Pipeline V2 (see `docs/future/ContinuousIngestion.md` / `docs/future/RetrievalOptimisation.md` for where these are tracked instead).

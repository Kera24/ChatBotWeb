# ADR-0033: Retain `dense_only` Retrieval — `hybrid_rrf` Not Promoted

Status: Accepted
Date: 2026-08-11

## Context

ADR-0032's "Future reconsideration triggers" identified hybrid retrieval as the direct fix for the 28-case `answerable_factual` "correct document never ranks in top-K" gap. Retrieval V2 Phase 1 implemented `hybrid_rrf` (`app.services.lexical_search` + `app.services.retrieval_fusion`, Reciprocal Rank Fusion of dense + PostgreSQL full-text candidates) alongside the existing `dense_only` baseline, config-driven via `settings.RETRIEVAL_STRATEGY`, with `dense_only` remaining the default. This ADR records the controlled bake-off's outcome and the resulting promotion decision.

An initial bake-off attempt used `LocalMockEmbeddingProvider` (SHA-256 hash-based, non-semantic — see `docs/architecture/vector-storage.md`) because the SQLite evaluation path re-embeds every candidate chunk on every case, making a real-embedding run against the 104-case `chunking_dataset.json` impractically slow. That mock run showed a large apparent hybrid improvement, but was not trustworthy: mock dense scores carry no real signal, so `dense_only`'s mock-mode numbers are artificially crippled and the comparison is not production-representative. A `CachingEmbeddingProvider` (`app.evaluation.embedding_cache`) was added — memoises `embed()` by exact `(provider, model, dimension, content-hash)`, evaluation-only, never touching production retrieval — cutting real Ollama embedding calls on the 104-case run from ~11,800+ to 217, making a genuine real-embedding bake-off practical (a few minutes instead of being killed for taking too long).

## Decision

**Retain `RETRIEVAL_STRATEGY=dense_only` as the production default. Do not promote `hybrid_rrf`.**

### Evidence

Real embeddings throughout: `nomic-embed-text-v2-moe`, `structure_aware` chunking, threshold 0.32 (ADR-0032), same prompts/guardrails/generation config, both arms run against the identical seeded corpus.

**Golden dataset** (14 chunks — every document shorter than one chunk, previously documented as too undifferentiated to meaningfully test retrieval-strategy differences): `hybrid_rrf` (wide pools, `final_top_k=5`) shows a small positive delta — pass rate 94.0%→95.2%, hit rate/recall@k 89.2%→91.9%, 0 new hard failures, but precision@k collapses 55.8%→21.6% and tokens +41%.

**Chunking-focused dataset** (113 chunks, 104 cases — the corpus purpose-built to exercise the exact ranking gap ADR-0032 identified, and the more decisive signal since the golden corpus barely differentiates strategies at all):
- `hybrid_rrf` at `final_top_k=5` (the best candidate from prior mock-mode experiments, tested here without assuming it would still win): pass rate 61.5%→58.7% (**regression**), hit rate/recall@k 67.0%→62.6%/62.1% (**regression**), evidence coverage 100%→87.5% (**regression**), hard failures 10→9, tokens −31%.
- `hybrid_rrf` at `final_top_k=10` (matching `dense_only`'s context window — one-variable-at-a-time follow-up): pass rate, hard failures, and hit rate/recall@k all **exactly tie** `dense_only` (61.5%/10/67.0%), precision@k slightly worse (24.4%→21.4%), tokens **+13.5%**.

Neither tested `hybrid_rrf` configuration delivers the required "answerable recall materially improves" on the corpus this feature exists to fix. Citation integrity (100% both arms, both corpora) and tenant/workspace/knowledge-scope isolation (existing + new unit and orchestrator-level tests) remain perfect in every configuration.

### Known-regression root cause (mock-mode session)

An earlier mock-embedding run showed `hybrid_rrf` uniquely breaking one case ("maximum number of matrix build combinations"). Traced end-to-end with real embeddings against the actual corpus: the correct chunk ranks **#1 in dense, #1 in lexical, and #1 in the fused top-5** — retrieval (dense ranking, lexical ranking, RRF fusion) is fully correct. The case fails identically under **both** strategies because `app.ai.guardrails.evidence_sufficiency.evaluate_chunk_support`'s numeric-value extraction returns `value_missing` (not `direct_support`) for the phrasing "a maximum of 25 matrix combinations." This is a pre-existing guardrail value-extraction limitation, not a retrieval defect and not hybrid-specific — the mock-mode-only "regression" was an artifact of non-semantic mock scores, not real. Not patched, per this task's explicit scope (guardrail changes require separate, explicit instruction — see `CLAUDE.md`).

## Alternatives

- **Promote `hybrid_rrf` as default now** — rejected: fails the "recall materially improves" and "non-regressive overall pass rate" criteria on the corpus that matters most for this decision.
- **Tune further (dense/lexical pool size, RRF k) before deciding** — partially explored (`final_top_k` 5 vs 10, one variable at a time, per this task's constraint); the pattern (best case: parity at higher cost; worse case: regression) did not suggest a further pool/k change would flip the outcome, and the embedding threshold/chunking/prompts/guardrails were correctly held constant throughout, per instruction. Left as a future reconsideration trigger below rather than exhausted.
- **Promote for a narrow exact-term-query subset only** — not evaluated; would require its own case-level classification and evaluation slice, out of this task's scope.

## Tradeoffs

- Retaining `dense_only`: no regression risk, no token/latency cost increase, but the 28-case `answerable_factual` ranking gap ADR-0032 identified remains unresolved.
- `hybrid_rrf` is fully implemented, tested (unit, integration, orchestrator end-to-end, real PostgreSQL full-text tier — see Validation), and available via one config value (`RETRIEVAL_STRATEGY=hybrid_rrf`) for any future reconsideration — the Phase 1 engineering investment is not wasted, only not activated by default.

## Consequences

- `settings.RETRIEVAL_STRATEGY` default remains `"dense_only"`; no production behavior changes as a result of this task.
- `hybrid_rrf` remains config-driven opt-in — rollback (were it ever enabled) is the same one-line config change.
- `app.evaluation.embedding_cache.CachingEmbeddingProvider` is retained regardless of this decision — it is a pure evaluation-performance fix (default-on in `run_evaluation`), independently valuable for any future real-embedding bake-off (chunking strategy, embedding model, threshold, or a future retrieval candidate).

## PostgreSQL production-path validation

Real `PostgreSQL + pgvector` integration tier (`docker compose`'s `postgres` service, `pgvector/pgvector:pg16`) executed twice consecutively: 23/23 tests passing both runs (exact lexical retrieval, `ts_rank_cd` ranking, `websearch_to_tsquery` behavior, org/workspace/assistant-scope isolation, ready/archived filtering, `document_ids=None`/`[]` semantics, repeated-run isolation). The `0021_lexical_search_index` migration's GIN index was independently confirmed to be created by a real `alembic upgrade head` run and removed by `downgrade -1`, directly against this Postgres instance (not just via `Base.metadata.create_all`, which the integration test suite itself uses).

## Future reconsideration triggers

- A completed real-embedding bake-off after reranking or query rewriting land (both explicitly out of scope for this task) — those may address the ranking gap more directly than lexical fusion alone.
- A different RRF k, or a query-classifier that routes only exact-term/code/SKU-shaped queries to `hybrid_rrf`, evaluated with the same real-embedding, same-corpus methodology this ADR used.
- A larger or more diverse real customer corpus becomes available for the bake-off — both `golden_dataset.json` (14 chunks) and `chunking_dataset.json` (113 chunks) are synthetic and may not represent real tenant corpus size/shape.
- The `evidence_sufficiency` numeric-value-extraction limitation documented above is fixed independently (a guardrail-layer task, not this one) — re-run this bake-off afterward, since it affects both strategies' case counts today and may currently be masking a small part of either arm's true recall.

# Caching V2 (General-Purpose Caching Layer)

## Purpose

Introduce a real caching layer (query/embedding/HTTP-level) to reduce latency and cost for repeated or near-duplicate work, beyond the narrow grader-result cache that exists today.

## Current limitation

`docs/engineering/caching.md` — the only cache in the codebase is `GraderResultCache` (evaluation-run-scoped, in-process). No caching exists for retrieval, embeddings, or generation.

## Why postponed

No measured evidence yet that redundant computation (repeated embedding calls, repeated retrieval for near-duplicate queries) is a real cost/latency problem in production; building a cache without that evidence risks solving the wrong problem or introducing staleness bugs for no benefit.

## Dependencies

- `docs/architecture/observability.md`'s cost/latency trace data, to identify what's actually worth caching.
- A tenant-isolation-safe cache-key design (any cache must be scoped at least as tightly as the existing knowledge-scope boundary — see `docs/engineering/caching.md`'s out-of-scope note).

## Implementation phases

1. Identify the highest-value cache target from observability data (likely embeddings for repeated/near-duplicate ingestion or query text).
2. Add an embedding cache (content-hash keyed, per-tenant scoped) as the first real cache layer.
3. Evaluate a semantic query cache separately — see `docs/future/SemanticCache.md`, which is a distinct, higher-risk design (answer-level caching, not just embedding-level).

## Technical design

Likely a Redis-backed cache (Redis is already present in `docker-compose.prod.yml` for rate limiting) keyed by content hash + tenant scope, with explicit TTL — no cache entry lives forever by default.

## Evaluation plan

Measure cache hit rate and resulting latency/cost reduction against the observability baseline established before building it; verify no staleness-driven answer-quality regression.

## Rollback strategy

Cache-miss must always be a safe fallback to the uncached path (never a hard dependency) — disabling the cache should be a flag flip with zero functional change, only a performance/cost change.

## Success metrics

Measured latency and cost reduction (embedding/provider call volume) with zero tenant-isolation incidents and no evaluation-score regression.

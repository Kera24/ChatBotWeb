# Semantic Cache

## Purpose

Cache full answers for semantically near-duplicate questions (not just exact-match caching), to cut latency and provider cost for commonly repeated question patterns.

## Current limitation

No caching exists between retrieval and generation (`docs/engineering/caching.md`); every question, even a near-exact repeat, re-runs the full pipeline including a provider call.

## Why postponed

Higher-risk than `docs/future/CachingV2.md`'s embedding-level caching: caching a full answer risks serving a stale or subtly-wrong answer if underlying documents changed, and "semantically near-duplicate" is a fuzzy match that can misfire (serving an answer to a question that wasn't actually the same). Needs `docs/future/CachingV2.md`'s simpler caching to land and prove the operational model first.

## Dependencies

- `docs/future/CachingV2.md` (general caching infrastructure/patterns).
- Document-version-aware cache invalidation (a cached answer must be invalidated when the source documents it was grounded in change).

## Implementation phases

1. Define similarity threshold and scope (per-workspace, per-assistant) for what counts as "near-duplicate" — conservative threshold first, wide open cache is out of scope.
2. Cache keyed by (query embedding neighborhood, assistant knowledge-scope hash, active document versions) so any document change invalidates affected cache entries.
3. Serve cached answer only when a fresh evidence-sufficiency/citation check still passes against current documents — never serve a cached answer that skips guardrails entirely.

## Technical design

Cache lookup happens before the provider call but after retrieval — retrieved evidence is still checked against the cached answer's citations for continued validity, so guardrail logic is never bypassed, only the provider call is skipped on a hit.

## Evaluation plan

Cache hit rate, latency/cost reduction, and — critically — a staleness audit (sampled cache hits manually verified against current source documents) before wide rollout.

## Rollback strategy

Cache-miss is always a safe, correct fallback to the full pipeline; disabling is a flag flip. Any single bad cached answer can be invalidated by the same document-version-change mechanism used for normal invalidation.

## Success metrics

Meaningful latency/cost reduction on repeated question patterns with zero measured staleness incidents in the evaluation audit.

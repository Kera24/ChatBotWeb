# Caching — Current / Future / Out of Scope

## Current

No general-purpose caching layer exists. The only cache in the codebase is `GraderResultCache` (`apps/api/app/evaluation/graders/cache.py`) — an in-process dict keyed by a SHA-256 hash of `(dimension, context, rubric_version, grader_model)`, used only to avoid re-grading identical answer/evidence/rubric/model combinations within an evaluation run. There is no query-result cache, embedding cache, HTTP response cache, or Redis-backed cache for the retrieval or generation paths. `docs/architecture/retrieval.md` and `docs/architecture/memory.md` have no caching section because none exists to document.

## Future

- Semantic query cache (near-duplicate question → cached answer) — see `docs/future/SemanticCache.md`.
- Embedding cache for repeated/near-duplicate ingestion or query text — see `docs/future/CachingV2.md`.
- A caching ADR once a real caching layer is designed (none of ADRs 0001-0018 cover caching).

## Out of scope (not planned)

- Caching model-generated answers verbatim across different tenants/workspaces — any future cache stays scoped per-tenant at minimum, matching the existing knowledge-scope isolation invariant.

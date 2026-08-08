# Memory — Current / Future / Out of Scope

## Current

No multi-turn conversation memory — every RAG question is answered independently of prior turns in the same conversation. Full detail: `docs/architecture/memory.md`.

## Future

- Conversation-scoped short-term memory (recent-turn context injected into retrieval/prompting) — see `docs/future/MemoryV2.md`.
- Long-term per-user/per-workspace memory (preferences, recurring context) as a distinct, later phase after short-term memory proves out — see `docs/roadmap/roadmap.md`.

## Out of scope (not planned)

- Cross-tenant or cross-workspace memory of any kind — memory, if built, stays scoped at least as tightly as the existing knowledge-scope/tenant-isolation boundary.

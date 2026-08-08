# Memory Checklist

Applies once `docs/future/MemoryV2.md` is implemented.

## Required validation

- Multi-turn evaluation case set run (must be built as part of the first memory implementation — none exists today).
- Single-turn evaluation case set re-run to confirm no regression to non-memory behavior.

## Things to verify

- Memory context is scoped at least as tightly as the existing knowledge-scope/tenant-isolation boundary — no cross-tenant or cross-conversation leakage.
- Explicit privacy review completed before any rollout (what's remembered, for how long, visible to whom).
- Memory injection is traceable (what context was injected, per request) via observability.
- Memory can be disabled per-conversation/per-tenant via flag with zero functional regression to the non-memory path.

## Common mistakes

- Injecting memory context without a corresponding trace record, making it invisible to debugging.
- Skipping the privacy review because "it's just conversation history."
- Not building the multi-turn case set before claiming evaluation coverage.

## Required documentation

- Update `docs/engineering/memory.md`/`docs/architecture/memory.md` once any memory capability ships (today: "no multi-turn conversation memory" is the accurate, documented current state).

## Definition of Done

Multi-turn case set exists and passes; privacy review completed and recorded; memory injection traceable; flag-disable path verified to fully revert to current no-memory behavior.

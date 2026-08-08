# Testing — Current / Future / Out of Scope

## Current

Backend pytest with per-file fixtures (no shared `conftest.py`), frontend Vitest+Testing Library co-located `*.test.tsx`, widget/SDK own Vitest suites, Playwright e2e in `tests/widget-browser/`. `test_rag_orchestrator.py` is the primary regression guard for the whole RAG pipeline. Full detail: `docs/architecture/testing.md`.

## Future

- Broader synthetic/production-sample-driven evaluation test coverage as continuous evaluation matures — see `docs/roadmap/roadmap.md`.
- Load/perf testing tied to the scaling roadmap's migration triggers — see `docs/engineering/scaling-strategy.md`.

## Out of scope (not planned)

- Introducing a shared global `conftest.py` for the backend — the per-file fixture convention is deliberate (isolation over DRY) and stays unless explicitly revisited.

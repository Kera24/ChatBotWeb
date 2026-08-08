# Performance Checklist

## Required validation

- Latency/cost comparison against baseline using observability trace data (`docs/architecture/observability.md`) from a staging or test run.

## Things to verify

- p95 latency for the affected request path is not materially regressed, or the regression is explicitly justified (e.g. traded for quality).
- No new N+1 query pattern introduced (check repository function usage against the ORM's eager/lazy-load conventions already in place).
- Any new pipeline stage's cost (in latency or provider tokens) is accounted for, not just its correctness.
- Caching (where it already exists — `docs/engineering/caching.md`'s `GraderResultCache`) is not broken by the change.

## Common mistakes

- Only benchmarking the happy path, not the fallback/guardrail-blocked path (which can have different latency characteristics).
- Not measuring cost impact for a change that adds a provider call.

## Required documentation

- Note the before/after comparison in the PR/report if the change is performance-sensitive.

## Definition of Done

Latency/cost comparison performed and reported; no unexplained regression; new pipeline stages accounted for in the cost model.

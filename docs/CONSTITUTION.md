# Conversa Project Constitution

This document defines how Conversa is built, not just what it does. For product mission and architectural/AI-safety principles, `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md` is the canonical source — this document does not repeat it, only extends it with engineering operating philosophy, launch/scaling strategy, and long-term platform vision.

## Mission

See `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md` ("Mission" and "Product promise"). In one line: give any organisation a reliable, source-grounded AI assistant over its own knowledge, without developer intervention to keep it current.

## Vision

Conversa starts as a website-widget assistant product and is architected as the foundation of a reusable AI Core (see the Manifesto's "Platform before channel" principle) — the same knowledge/retrieval/prompt/provider/conversation/evaluation/cost systems should be able to power future channels (Teams/Slack integrations, internal staff assistants, voice, agentic workflows) without being rewritten. Every architectural decision is evaluated against "does this stay channel-independent," not just "does this ship the widget."

## Engineering philosophy

- **Boring technology, deliberately.** Plain CSS over a component framework, a dataclass `Settings` over a config library, functional repositories over an ORM abstraction layer. Fewer moving parts is a feature, not a gap, at this stage of the platform's life (see the Manifesto's "Evolution without premature complexity").
- **Contracts before code.** New endpoints, new trace fields, new schema changes are additive (new optional trailing fields, new tables) rather than breaking, so existing callers and tests never need to change just because a new feature was added nearby.
- **Fail-safe by construction.** Cross-cutting instrumentation (telemetry, trace recording, redaction) must never be able to break the feature it observes. Wrap in try/except, default to no-op, prove it with a test that deliberately breaks the instrumentation and asserts the primary path still succeeds.
- **Read before you write.** Every non-trivial change starts by reading the actual current implementation and its tests, not by pattern-matching from memory or from a similar-looking codebase.

## Product philosophy

- Prefer an honest fallback over an unsupported answer (Manifesto: "Source-grounded intelligence"). This is the platform's core trust promise and overrides feature convenience every time.
- Multi-tenant isolation is an invariant, not a checklist item — see `docs/architecture/authentication.md` and `docs/file-boundaries.md` for where the boundary is enforced in code.
- Quality is a measured property of the system (evaluation scores, guardrail trigger rates, review-confirmed error rates), not an assumed one.

## Architecture philosophy

See `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`'s "Architectural principles" section in full (platform-before-channel, multi-tenant by construction, provider independence, reusable AI Core, explicit lifecycle and versioning, observable and cost-aware, secure defaults). `docs/architecture/overall-system.md` maps these principles onto the actual current file structure.

## AI philosophy

See the Manifesto's "AI safety principles." In practice in this codebase: the guardrail chain (`docs/architecture/guardrails.md`) is layered and each layer has one job; retrieval never crosses a tenant or knowledge-scope boundary; generated text is never persisted or returned without passing output-safety checks; provider/model/prompt are versioned so behavior is reproducible from a trace.

## Evaluation-first development

A change to retrieval, prompt assembly, guardrails, or the generation pipeline is not considered complete until the evaluation suite (`docs/architecture/evaluation.md`) has been run against it and the result is understood — even if thresholds don't move, an unexplained score change is a signal to investigate before shipping. Evaluation datasets, categories, and scoring are the closest thing this project has to a formal spec for "what does a good answer look like," and changing the bar itself requires explicit, deliberate instruction (see `CLAUDE.md`'s "things Claude must never do").

## Evidence-driven engineering

Every claim in a report to the user ("tests pass," "the build succeeds," "the feature works") must be backed by a command actually run in that session. When live-verifying a UI change is impractical in the current environment, say so explicitly rather than inferring success from a type check. See `docs/development-playbook.md`'s Validate step and `docs/reporting-policy.md`.

## Continuous improvement loop

Plan → Implement → Validate → Evaluate → Review → Deploy → Observe → Improve, detailed step-by-step in `docs/development-playbook.md`. The loop closes through observability (`docs/architecture/observability.md`) and evaluation (`docs/architecture/evaluation.md`): production/pilot signals about fallback rate, blocked rate, cost, and evidence-insufficient rate feed back into what gets prioritized next, rather than improvement being driven by intuition alone.

## Launch strategy

Controlled pilot on a single low-cost VPS via Docker Compose (`docker-compose.prod.yml`), not Azure, as the first production deployment target — see ADR `docs/adr/0027-vps-first-controlled-pilot-hosting.md` (which supersedes the original Azure-first hosting choice in `docs/adr/0018-controlled-pilot-production-hosting-and-observability-model.md`) and `docs/architecture/deployment.md`. The MVP scope and success definition are tracked in `docs/07_Roadmap/01_MVP_Implementation_Plan.md`. Launch readiness is a checklist of demonstrated behavior (tenant isolation enforced, grounded answers verified, evaluation gate passing, backups tested), not a date.

## Scaling strategy

Scale by extracting services only when operational evidence justifies it (Manifesto: "Evolution without premature complexity"), not preemptively. The current single-Postgres, single-API-process, Docker Compose model is expected to comfortably serve controlled-pilot and early-production traffic; the next scaling steps (read replicas, worker separation, managed Postgres/pgvector, horizontal API scaling) are deferred until real traffic data (via `docs/architecture/observability.md`'s metrics) shows the need.

## Deployment roadmap

1. **Now**: controlled pilot on a single VPS, Docker Compose, structured JSON logs + AI trace tables in Postgres as the minimum observability tier.
2. **Optional now**: the recommended-tier VPS observability stack (OTel Collector + Prometheus + Loki + Tempo + Grafana, `docker-compose.observability.yml`) for deployments that want infra-level dashboards without leaving the VPS.
3. **Future**: Azure migration path is kept live via `infrastructure/azure/` and the OpenTelemetry-first instrumentation choice — see `docs/02_Architecture/Azure_Monitor_Application_Insights_Mapping.md` for the concrete component-by-component mapping when that migration is undertaken. Azure is a documented option, not a current commitment.

## Design principles

See `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`'s "Design philosophy: controlled Expressionism" section and `docs/design/design-system.md` for the concrete tokens/components that implement it today.

## Long-term platform vision

The website widget is the first channel, not the ceiling. The reusable AI Core layers (knowledge ingestion, retrieval, prompt/provider abstraction, conversation model, evaluation framework, cost/observability) are designed so that a second channel (e.g. a Slack or Teams integration, an internal staff assistant, a voice interface) could be added as a new access-layer adapter (following the existing `app.access.channels.widget` pattern) without rewriting the AI core. Long-term success is measured by how cheaply a new channel can be added, not just by how good the current widget is.

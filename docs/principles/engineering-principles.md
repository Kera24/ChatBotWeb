# Engineering Principles

These principles govern how engineering decisions get made on Conversa. They are referenced throughout `docs/adr/*.md`, `docs/engineering/*.md`, and `docs/future/*.md` — when those documents cite a principle, this is the canonical definition.

## 1. Evaluation-first engineering

No material change to retrieval, generation, guardrails, or prompts ships without being measured against the evaluation framework (`docs/architecture/evaluation.md`). This is why the evaluation framework was built before guardrails (`docs/adr/0021-evaluation-before-guardrails.md`) and before graders (`docs/adr/0022-guardrails-before-graders.md`) — you cannot evaluate what you haven't built the means to measure.

## 2. Evidence-based decisions

Architectural decisions are justified by measured evidence (observability traces, evaluation scores, calibration data), not assumption or intuition. `docs/adr/0024-observability-before-scaling.md` and `docs/adr/0020-delay-qdrant-migration.md` are direct applications: scaling and vector-store-migration decisions wait for data, not projection.

## 3. No feature without evaluation

A feature that changes what an assistant retrieves, generates, or blocks must have evaluation coverage before it's considered done — not as a follow-up task. This is why every `docs/future/*.md` spec includes an "Evaluation plan" section as a required part of the spec itself, not an afterthought.

## 4. No regression acceptance

`app.evaluation.policy`/`gate` thresholds exist to prevent shipping a change that measurably makes answers worse, and they are never loosened to unblock a specific change (`docs/engineering/evaluation.md`, `CLAUDE.md`). A failing evaluation gate is a signal to fix the change, not the gate.

## 5. Production-first mindset

Design and validate against what will actually run in production (real request shapes, real tenant isolation boundaries, real failure modes), not idealized conditions. The fail-safe observability recorder pattern (never let trace-recording failure break a real request — `docs/architecture/observability.md`) and the explicit fallback-not-silent-failure semantics of the RAG pipeline (`docs/architecture/retrieval.md`) are both direct expressions of this.

## 6. Security-first

Tenant isolation, RBAC, and redaction are structural, not optional add-ons — every route enforces `require_organisation_role()`, every query is scoped by `organisation_id`/`workspace_id`, and trace/log content is redacted by default (`docs/engineering/security.md`). Security properties are verified the same way correctness is: with tests, not just review.

## 7. Observability-first

Understand production behavior before trying to change it at scale. `docs/adr/0024-observability-before-scaling.md` is this principle's clearest expression: AI observability was built before any scaling-oriented feature work began, specifically so scaling decisions would have real data behind them.

## 8. Scalability by abstraction

Scale-sensitive subsystems (vector storage, AI providers, deployment target) sit behind explicit interfaces (`app.services.vector_search`, `app.ai.provider_registry.ProviderRegistry`) so that scaling them later is a swap behind the boundary, not a rewrite of everything that depends on them. `docs/adr/0019-postgresql-pgvector-over-dedicated-vector-database.md` and `docs/adr/0020` rely on this directly — the pgvector-to-Qdrant migration path only stays open because the abstraction is honest.

## 9. Vendor independence

No single vendor/provider is load-bearing in a way that would be expensive to replace. The `AIProvider` interface (`docs/architecture/retrieval.md`), the `BillingGateway` Protocol (`docs/engineering/billing.md`), and the OpenTelemetry-first instrumentation choice (which keeps both Azure Monitor and a generic OTLP path viable, `docs/architecture/observability.md`) are all direct applications.

## 10. Progressive enhancement

Ship the simplest thing that works for current scale/needs, and add complexity only when evidence justifies it — not ahead of need. `docs/adr/0027-vps-first-controlled-pilot-hosting.md` (VPS before Azure), `docs/adr/0026-manual-ingestion-before-connectors.md` (manual upload before connectors), and `docs/adr/0020` (delay Qdrant) are all instances of this same principle.

## 11. Cost-aware engineering

Infrastructure and provider spend is justified by need, not held "just in case." `docs/adr/0029-retain-azure-architecture-without-deploying.md` explicitly weighed this: Azure IaC is kept (cheap to retain, expensive to rebuild from scratch) but not deployed (real ongoing cost with no current benefit). `docs/future/CostOptimisation.md` and `docs/future/GPUWorkers.md` apply the same lens to future AI provider and infrastructure spend.

## How these principles relate to each other

Principles 1-4 (evaluation-first, evidence-based, no-feature-without-evaluation, no-regression) form one cluster: nothing ships or scales without measurement. Principles 5-7 (production-first, security-first, observability-first) form a second cluster: understand and protect what's actually running before changing it. Principles 8-11 (scalability by abstraction, vendor independence, progressive enhancement, cost-aware) form a third cluster: build the simplest correct thing today while keeping tomorrow's harder version cheap to reach. When principles appear to conflict on a specific decision (e.g. progressive enhancement vs. scalability by abstraction), the resolution favors evidence over speculation — the same test principle 2 already sets.

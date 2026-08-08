# Engineering Priority Matrix

Every `docs/future/*.md` specification categorized into one priority bucket. Cross-reference `docs/roadmap/roadmap.md` for Completed/In Progress/Planned/Deferred status and `docs/engineering/implementation-order.md` for the detailed dependency reasoning behind the ordering — this document answers "how important/urgent," those answer "what's done" and "in what order," respectively.

## A note on "Before Launch"

Conversa has already launched (controlled pilot, VPS — `docs/roadmap/roadmap.md`'s Completed section). The categories below are the standard scheme requested, applied honestly: **Critical Before Launch** and **Nice Before Launch** are populated with what those categories actually contained historically (all now `Completed`, not `docs/future/*.md` specs), so the historical record is accurate rather than force-fitting current specs into a pre-launch frame that no longer applies. Every one of the 27 future specs is necessarily a **post-launch** item and is categorized into one of the five categories that make sense post-launch.

## Critical Before Launch (historical — completed)

Evaluation framework, guardrails A-H, core RAG pipeline, RBAC/tenant isolation, billing, widget SDK/delivery. All shipped pre-launch; see `docs/roadmap/roadmap.md`'s Completed section.

## Nice Before Launch (historical — completed)

AI observability, calibrated model-based graders, prompt versioning. Shipped pre-launch but were not strictly launch-blocking in the way the "Critical" items were.

## Immediately After Launch

- `docs/future/EvaluationV2.md` — continuous evaluation; needed early so every later item gets a better evaluation signal.
- `docs/future/PromptOptimisation.md` — experimentation/shadow-testing; low-risk, high-leverage.
- `docs/future/RetrievalOptimisation.md` — chunking/threshold tuning; cheapest retrieval-quality improvement, no new infrastructure.

## Phase 1 Growth

- `docs/future/HybridRetrieval.md`, `docs/future/Reranking.md`, `docs/future/QueryRewrite.md` — retrieval-quality track, sequenced in that order (`docs/engineering/implementation-order.md`).
- `docs/future/MemoryV2.md` — short-term conversation memory.
- `docs/future/ConnectorFramework.md`, `docs/future/ContinuousIngestion.md` — demand-gated, can proceed in parallel with the retrieval/memory track.
- `docs/future/ModelRouting.md`, `docs/future/CostOptimisation.md` — gated on a second live provider existing.
- `docs/future/ObservabilityV2.md` — deferred observability items (rollup tables, richer alerting) as usage grows enough to justify them.
- `docs/future/GuardrailsV2.md` — wiring `grounding.py` in, via shadow-mode validation.

## Phase 2 Scale

- `docs/future/CachingV2.md`, `docs/future/SemanticCache.md` — evidence-driven caching once redundant computation is measured.
- `docs/future/EmbeddingBakeoff.md` — needs production-scale evaluation data to be meaningful.
- `docs/future/QdrantMigration.md`, `docs/future/DistributedArchitecture.md` — evidence-triggered infrastructure scaling (~1,000-10,000 customer tier, `docs/engineering/scaling-strategy.md`).
- `docs/future/ScalingRoadmap.md`, `docs/future/DeploymentRoadmap.md` — the roadmap/sequencing documents governing this tier and the Azure-activation tier beyond it.
- `docs/future/GPUWorkers.md` — self-hosted model infrastructure, cost/latency/residency-driven.
- `docs/future/MultimodalKnowledge.md` — needs a multimodal-capable provider.

## Enterprise

- `docs/future/EnterpriseSSO.md`, `docs/future/ComplianceRoadmap.md`, `docs/future/EnterpriseRoadmap.md` (umbrella) — all gated on a concrete enterprise-tenant requirement, per `docs/adr/0026-manual-ingestion-before-connectors.md`'s demand-evidence standard applied to enterprise features generally.

## Long-term Research

- `docs/future/KnowledgeGraph.md` — highest-complexity retrieval item; needs hybrid retrieval/reranking mature plus observed multi-hop-question failures.
- `docs/future/AgentFramework.md` — highest-complexity item overall; needs memory, model routing, and evaluation/observability maturity all in place first.

## How to use this matrix

When prioritizing engineering work, check a candidate feature against this matrix first. If it maps to an existing category, that's the starting priority signal (subject to override by real evidence — a Phase 2 item can move up if a Phase 1-tier trigger condition is unexpectedly met early, per `docs/principles/engineering-principles.md`'s evidence-based-decisions principle). If a new future spec is added that isn't yet in this matrix, categorize it here as part of writing the spec, not as a separate later step.

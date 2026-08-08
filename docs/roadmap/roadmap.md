# Engineering Roadmap

Every phase below is marked **Completed**, **In Progress**, **Planned**, or **Deferred**. This roadmap is the sequencing layer over the individually specced items in `docs/future/*.md`; see `docs/engineering/implementation-order.md` for the detailed dependency reasoning behind the ordering, and `docs/adr/*.md` for the decision record behind each major choice.

## Completed

- **Launch MVP** — core multi-tenant platform (Organisation → Workspace → Assistant), RAG pipeline, guardrails A-H, widget SDK/iframe delivery, billing (Stripe), dashboard. See `docs/architecture/overall-system.md`.
- **Evaluation Foundation** — Dataset → Case → Run → Result framework, deterministic launch-gating scoring. `docs/adr/0021-evaluation-before-guardrails.md`, `docs/adr/0025-deterministic-evaluation-gates.md`.
- **Guardrails** — layers A-H wired into the live pipeline. `docs/adr/0022-guardrails-before-graders.md`, `docs/adr/0023-evidence-sufficiency-as-a-dedicated-layer.md`.
- **Calibrated Model-Based Graders** — rubric grading engine, calibration harness, advisory-only pending calibration evidence. `docs/engineering/graders.md`.
- **Prompt Versioning** — immutable versioned prompts, lifecycle states, per-message traceability. ADR 0003.
- **AI Observability** — trace model, redaction, cost accounting, dual-path OTel, RBAC-scoped API/UI, deterministic anomaly/drift signals. `docs/adr/0024-observability-before-scaling.md`, `docs/architecture/observability.md`.
- **VPS Production Launch** — single-VPS controlled-pilot deployment, backup/restore, rollback runbooks. `docs/adr/0027-vps-first-controlled-pilot-hosting.md`.
- **Developer Operating System** — `CLAUDE.md`, `docs/architecture/`, `.skills/`, `.prompts/`, validation/reporting/file-boundary policy. `docs/adr/0030-developer-operating-system.md`.
- **Engineering Brain** — this document set (`docs/engineering/`, `docs/adr/`, `docs/future/`, `docs/roadmap/`, `docs/principles/`). `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md`.

## In Progress

- **Production Stabilisation** — closing known interim gaps: email delivery for password reset/verification (currently stubbed, `docs/engineering/authentication.md`), tightening the "tenant context as query param" pattern once session-based auth is trusted enough.

## Planned

Ordered roughly as `docs/engineering/implementation-order.md` sequences them; see that document for the full dependency reasoning.

- **A Real (Non-Mock) AI Provider** — prerequisite for nearly everything below; `docs/architecture/retrieval.md`'s "Providers" section.
- **Continuous Evaluation** — production-trace-sampled evaluation runs, not just pre-release datasets. `docs/future/EvaluationV2.md`.
- **Experimentation / Prompt Optimisation** — A/B and shadow-testing between prompt versions. `docs/future/PromptOptimisation.md`.
- **Production Feedback Loop** — closing the loop from observability signals back into evaluation case sets and prompt/guardrail tuning. `docs/future/EvaluationV2.md`, `docs/future/GuardrailsV2.md`.
- **Memory Improvements (short-term)** — conversation-scoped context injection. `docs/future/MemoryV2.md`.
- **Retrieval Optimisation, Hybrid Retrieval, Reranking, Query Rewrite** — `docs/future/RetrievalOptimisation.md`, `docs/future/HybridRetrieval.md`, `docs/future/Reranking.md`, `docs/future/QueryRewrite.md`.
- **Connector Framework, Continuous Ingestion** — automated knowledge sources beyond manual upload. `docs/future/ConnectorFramework.md`, `docs/future/ContinuousIngestion.md`.
- **Model Routing** — once a second live provider exists. `docs/future/ModelRouting.md`.
- **Caching V2, Semantic Cache** — evidence-driven, once observability shows redundant work worth caching. `docs/future/CachingV2.md`, `docs/future/SemanticCache.md`.
- **Cost Optimisation** — once real provider cost data exists. `docs/future/CostOptimisation.md`.
- **Scaling (evidence-triggered)** — `docs/future/ScalingRoadmap.md`, `docs/engineering/scaling-strategy.md`.

## Deferred

Specced but intentionally not started — each waits on a named trigger, not a calendar date.

- **Qdrant Migration** — waits on measured pgvector bottleneck. `docs/adr/0020-delay-qdrant-migration.md`, `docs/future/QdrantMigration.md`.
- **Azure Scale (activation)** — waits on scale/compliance triggers; IaC retained. `docs/adr/0029-retain-azure-architecture-without-deploying.md`, `docs/future/DeploymentRoadmap.md`.
- **Distributed Architecture** — waits on single-VPS capacity limits. `docs/future/DistributedArchitecture.md`.
- **Multimodal Knowledge** — waits on a multimodal-capable provider. `docs/future/MultimodalKnowledge.md`.
- **Knowledge Graph** — waits on hybrid retrieval/reranking maturity and observed multi-hop-question failure patterns. `docs/future/KnowledgeGraph.md`.
- **Long-Term Memory** — waits on short-term memory proving out first. `docs/future/MemoryV2.md`.
- **Enterprise Features (SSO, Compliance)** — wait on a concrete enterprise-tenant requirement. `docs/future/EnterpriseSSO.md`, `docs/future/ComplianceRoadmap.md`, `docs/future/EnterpriseRoadmap.md`.
- **Agentic Features** — waits on memory, model routing, and evaluation/observability maturity; the most speculative item in the roadmap. `docs/future/AgentFramework.md`.
- **GPU Workers** — waits on a self-hosted-model decision. `docs/future/GPUWorkers.md`.
- **Embedding Bake-off** — waits on production-scale evaluation data. `docs/future/EmbeddingBakeoff.md`.

## Long-term platform vision

The direction beyond any single phase above: one core RAG/guardrail/evaluation engine, reachable through multiple channels (website widget today, others later — `docs/future/AgentFramework.md`), scaling from pilot to enterprise without a rewrite, with every material step justified by observability/evaluation evidence rather than assumption. See `docs/CONSTITUTION.md`'s "Long-term platform vision" for the full framing and `docs/engineering/scaling-strategy.md` for the concrete scale tiers.

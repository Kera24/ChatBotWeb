# Engineering Index

The master index of Conversa's engineering memory — the "Engineering Brain." Every architectural decision, current-state reference, and future plan is discoverable from this page. Start here for any non-trivial engineering task.

**Related but distinct**: `CLAUDE.md` (repo root) and `docs/README.md` are the entry points for the "Developer Operating System" (coding conventions, validation commands, file boundaries, reusable prompts/skills — `docs/adr/0030-developer-operating-system.md`). This index is for engineering *reasoning*: what exists, why, and what's planned. Use both together — the operating system tells you *how* to work, this index tells you *what you're working within*.

## How to use this index

1. **Working on an existing subsystem?** Start with its `docs/engineering/*.md` page (current/future/out-of-scope), then its deeper `docs/architecture/*.md` page if one exists (linked from the engineering page), then any cited ADRs for the *why*.
2. **Proposing a new feature or change?** Check `docs/future/*.md` first — it may already be specced. Check `docs/roadmap/roadmap.md` for its current phase status and `docs/priorities/priority-matrix.md` for its priority tier. Check `docs/engineering/implementation-order.md` for whether it has unmet dependencies.
3. **Making an architectural decision?** Read `docs/principles/engineering-principles.md` first. Check whether an existing ADR already covers it. If not, write a new one following `docs/architecture/evolution-policy.md` and the existing template (Context, Decision, Alternatives, Tradeoffs, Consequences, Future reconsideration triggers) — see `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md` for why this is required, not optional.
4. **Trying to understand "why is it built this way"?** `docs/adr/*.md`, numbered chronologically, is the decision record.
5. **Doing the work itself (implementing, testing, deploying)?** Start at `docs/workflows/engineering-lifecycle.md` (or its AI/feature-specific specializations), use the matching `docs/checklists/*.md` while working, and consult `docs/sops/*.md`/`docs/runbooks/*.md` when something needs a defined procedure or has gone wrong.

## Current-state architecture (`docs/engineering/*.md`)

Each page uses a Current / Future / Out-of-scope structure; pages for subsystems with a deeper Task-2-era reference point into `docs/architecture/*.md`.

| Topic | File |
|---|---|
| System architecture | `docs/engineering/system-architecture.md` |
| Authentication | `docs/engineering/authentication.md` |
| Billing | `docs/engineering/billing.md` |
| Assistant architecture | `docs/engineering/assistant-architecture.md` |
| Knowledge ingestion | `docs/engineering/knowledge-ingestion.md` |
| Document processing | `docs/engineering/document-processing.md` |
| Chunking | `docs/engineering/chunking.md` |
| Embeddings | `docs/engineering/embeddings.md` |
| Vector storage | `docs/engineering/vector-storage.md` |
| RAG pipeline | `docs/engineering/rag-pipeline.md` |
| Memory | `docs/engineering/memory.md` |
| Caching | `docs/engineering/caching.md` |
| Conversation lifecycle | `docs/engineering/conversation-lifecycle.md` |
| Evaluation | `docs/engineering/evaluation.md` |
| Guardrails | `docs/engineering/guardrails.md` |
| Graders | `docs/engineering/graders.md` |
| Prompt versioning | `docs/engineering/prompt-versioning.md` |
| Observability | `docs/engineering/observability.md` |
| Analytics | `docs/engineering/analytics.md` |
| Deployment | `docs/engineering/deployment.md` |
| Security | `docs/engineering/security.md` |
| Testing | `docs/engineering/testing.md` |
| Release process | `docs/engineering/release-process.md` |
| AI system design (providers/models) | `docs/engineering/ai-system-design.md` |
| AI lifecycles (prompt/context/retrieval/memory/eval/guardrail/feedback) | `docs/engineering/ai-lifecycles.md` |
| Scaling strategy (100 / 1K / 10K / 100K customer tiers) | `docs/engineering/scaling-strategy.md` |
| Implementation order (dependency-ordered future work) | `docs/engineering/implementation-order.md` |

## Decision records (`docs/adr/`)

30 ADRs total. 0001-0018 predate this effort (multi-tenant platform, provider abstraction, prompt versioning, RAG orchestrator boundary, the full public-widget security/access bounded context, widget SDK/UI/deployment/publishing, original Azure-first pilot architecture). 0019-0030 were added by this effort:

| ADR | Decision |
|---|---|
| 0019 | PostgreSQL+pgvector over a dedicated vector database |
| 0020 | Delay Qdrant migration |
| 0021 | Evaluation before guardrails (sequencing) |
| 0022 | Guardrails before graders (sequencing) |
| 0023 | Evidence sufficiency as a dedicated guardrail layer |
| 0024 | Observability before scaling |
| 0025 | Deterministic evaluation gates |
| 0026 | Manual ingestion before connectors |
| 0027 | VPS-first controlled pilot hosting (supersedes 0018's hosting choice) |
| 0028 | Engineering documentation as a first-class deliverable |
| 0029 | Retain Azure architecture without deploying |
| 0030 | Developer Operating System |
| 0031 | Promote structure-aware chunking to the default strategy |
| 0032 | Recalibrate the nomic-embed-text-v2-moe retrieval threshold for structure-aware chunking |
| 0033 | Retain dense_only retrieval — hybrid_rrf not promoted (real-embedding bake-off evidence) |

Full list with pre-existing 0001-0018: see `docs/adr/` directory or `docs/README.md`.

## Future feature specs (`docs/future/`)

27 specs, each with Purpose / Current limitation / Why postponed / Dependencies / Implementation phases / Technical design / Evaluation plan / Rollback strategy / Success metrics.

**Retrieval & knowledge**: `HybridRetrieval.md`, `Reranking.md`, `QueryRewrite.md`, `RetrievalOptimisation.md`, `KnowledgeGraph.md`, `EmbeddingBakeoff.md`, `QdrantMigration.md`
**Ingestion**: `ConnectorFramework.md`, `ContinuousIngestion.md`, `MultimodalKnowledge.md`
**Memory & caching**: `MemoryV2.md`, `CachingV2.md`, `SemanticCache.md`
**AI system**: `ModelRouting.md`, `PromptOptimisation.md`, `CostOptimisation.md`, `GPUWorkers.md`
**Evaluation & guardrails**: `EvaluationV2.md`, `GuardrailsV2.md`, `ObservabilityV2.md`
**Enterprise & compliance**: `EnterpriseSSO.md`, `ComplianceRoadmap.md`, `EnterpriseRoadmap.md`
**Scale & deployment**: `ScalingRoadmap.md`, `DeploymentRoadmap.md`, `DistributedArchitecture.md`
**Advanced**: `AgentFramework.md`

## Roadmap (`docs/roadmap/roadmap.md`)

Every phase marked Completed / In Progress / Planned / Deferred. The single place to check "is X done yet."

## Principles (`docs/principles/engineering-principles.md`)

11 principles governing how decisions get made: evaluation-first, evidence-based decisions, no feature without evaluation, no regression acceptance, production-first mindset, security-first, observability-first, scalability by abstraction, vendor independence, progressive enhancement, cost-aware engineering.

## Implementation order (`docs/engineering/implementation-order.md`)

The dependency-ordered sequence for everything in `docs/future/`, with reasoning for why each item comes after another.

## Engineering Workflow & Automation System

The operational layer: how work actually gets done, validated, shipped, and recovered — as opposed to the Engineering Brain's decisions/plans or the Developer Operating System's coding conventions. Every document below is process, not architecture.

### Workflows (`docs/workflows/`)

| Workflow | File |
|---|---|
| Master engineering lifecycle (Idea → Continuous Improvement, 21 stages) | `docs/workflows/engineering-lifecycle.md` |
| AI development lifecycle (per AI subsystem: embeddings, generation, prompts, retrieval, memory, evaluation, guardrails, graders, observability) | `docs/workflows/ai-development.md` |
| Feature development lifecycle (Idea → Retirement) | `docs/workflows/feature-development.md` |

### Checklists (`docs/checklists/`)

`frontend-checklist.md`, `backend-checklist.md`, `rag-checklist.md`, `evaluation-checklist.md`, `guardrails-checklist.md`, `observability-checklist.md`, `deployment-checklist.md`, `release-checklist.md`, `production-checklist.md`, `security-checklist.md`, `performance-checklist.md`, `billing-checklist.md`, `connector-checklist.md`, `retrieval-checklist.md`, `memory-checklist.md`. Each: required validation, things to verify, common mistakes, required documentation, Definition of Done.

### Standard Operating Procedures (`docs/sops/`)

22 SOPs covering: adding a new LLM, changing embedding models, changing vector databases, changing prompts, changing retrieval strategy, adding rerankers, adding hybrid retrieval, adding connectors, adding new data sources, deploying, hotfix, rollback, database migration, evaluation/guardrail/prompt/model failures, production incidents, customer-reported bugs, security incident, billing issue, authentication issue. Each: purpose, when to use, step-by-step process, validation, rollback, success criteria.

### Operational Runbooks (`docs/runbooks/`)

18 runbooks covering: production outage, high latency, high token cost, embedding service failure, vector database outage, LLM provider outage, billing outage, authentication outage, webhook failures, observability alerts, Azure migration, VPS recovery, database recovery, backup restore, evaluation failures, prompt regressions, connector failures, memory failures. Each: symptoms, diagnosis, recovery, validation, escalation, post-incident review.

### Release Management (`docs/releases/`)

`internal-release.md`, `alpha.md`, `beta.md`, `production.md`, `enterprise.md`, `emergency-hotfix.md` — each with entry/exit criteria, evaluation requirements, rollback, monitoring, approval requirements.

### Production Readiness Gates (`docs/production/readiness-gates.md`)

The concrete gate list every Production-type release must satisfy: tests, evaluation thresholds, regression checks, guardrails, observability, documentation, rollback, performance, security, deployment validation, customer readiness.

### Operations (`docs/operations/`)

| Document | Covers |
|---|---|
| `docs/operations/observability-workflow.md` | Offline evaluation → deployment → telemetry → dashboards → alerts → incident detection → root cause analysis → golden dataset update → regression testing → redeployment; integration with evaluation/guardrails/graders/prompt/model/embedding/retrieval versions. |
| `docs/operations/continuous-improvement.md` | The permanent loop: customer usage → telemetry → observability → failures → incident analysis → golden dataset → evaluation → architecture review → implementation → deployment → customer usage. |

### Connector Framework (`docs/connectors/`)

`docs/connectors/connector-framework.md` (lifecycle, auth, permissions, incremental sync, scheduling, rate limiting, retries, monitoring, testing, deployment, onboarding standards) and `docs/connectors/connector-roadmap.md` (the supported-connector list: M365/SharePoint/OneDrive, Google Workspace/Drive, Notion, Confluence, Slack, Teams, Dropbox, GitHub, REST APIs, databases, email, CRM).

### Scaling & Deployment Playbook (`docs/scaling/deployment-evolution.md`)

Infrastructure-stage view: Development → Local → Single VPS → Multiple VPS → Managed PostgreSQL → Qdrant → Azure → Enterprise → Multi-region → Global. Companion to `docs/engineering/scaling-strategy.md`'s customer-count-tier view — read both together.

### Engineering Priority Matrix (`docs/priorities/priority-matrix.md`)

Every `docs/future/*.md` spec categorized: Critical/Nice Before Launch (historical), Immediately After Launch, Phase 1 Growth, Phase 2 Scale, Enterprise, Long-term Research.

### Architecture Evolution Policy (`docs/architecture/evolution-policy.md`)

The required process for major architectural changes (ADR, spec, review, evaluation, regression testing, observability, rollback plan, deployment strategy), with worked examples against real `docs/future/*.md` items.

## Relationship to the Developer Operating System and Engineering Workflow System

| Engineering Brain (decisions & plans) | Developer Operating System (conventions) | Engineering Workflow & Automation System (process) |
|---|---|---|
| `docs/adr/` — why decisions were made | `CLAUDE.md` — how to work in this repo | `docs/workflows/` — the lifecycle work moves through |
| `docs/engineering/` — current/future/out-of-scope per topic | `docs/architecture/` — deep current-state reference per subsystem | `docs/checklists/` — per-domain verification |
| `docs/future/` — specced, postponed work | `.prompts/`, `.skills/` — reusable task templates | `docs/sops/`, `docs/runbooks/` — defined procedures and incident response |
| `docs/roadmap/`, `docs/principles/`, `docs/priorities/` | `docs/validation-policy.md`, `docs/file-boundaries.md`, `docs/reporting-policy.md` | `docs/releases/`, `docs/production/`, `docs/operations/`, `docs/connectors/`, `docs/scaling/` |

All three are permanent, all three are meant to be read before starting non-trivial work, and all three are kept consistent with each other — see the final cross-reference review performed as part of this effort and its Task 3 predecessor.

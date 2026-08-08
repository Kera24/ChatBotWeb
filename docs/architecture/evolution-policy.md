# Architecture Evolution Policy

How major architectural changes are introduced at Conversa. This policy exists because of a real, discovered gap: ADR 0018 selected an Azure-first architecture, but the platform actually launched VPS-first without that decision ever being formally recorded — `docs/adr/0027-vps-first-controlled-pilot-hosting.md` had to be written after the fact to reconcile documentation with reality (see that ADR's Context section). This policy is how that gap is prevented from recurring.

## What counts as a "major" architectural change

A change that: alters a documented ADR's decision, introduces a new stateful service/dependency, changes the deployment target, changes the data model in a way that affects more than one subsystem, or changes how a core pipeline (RAG orchestration, guardrails, evaluation) is structured. A change that stays within an existing pattern (a new endpoint following the existing RBAC/repository shape, a new React component following the existing page/loader/component split) is not "major" under this policy, even if it's a large amount of code.

## Required steps for every major change

1. **ADR** — write it *before or during* implementation, not after. State Context, Decision, Alternatives, Tradeoffs, Consequences, and Future reconsideration triggers, following the format established in `docs/adr/0019`-`0030`. If the change reverses or supersedes an existing ADR, say so explicitly in the new ADR's header (`Supersedes: docs/adr/NNNN-...md`) — never leave the old ADR's decision silently contradicted by reality, as happened with 0018.
2. **Technical Specification** — concrete design following `docs/workflows/engineering-lifecycle.md`'s Technical Design and Specification stages.
3. **Architecture Review** — checked against `docs/engineering-index.md`, the relevant `docs/architecture/*.md`/`docs/engineering/*.md` pages, and `docs/principles/engineering-principles.md`.
4. **Evaluation** — if the change touches the AI pipeline, full evaluation-gate validation (`docs/checklists/evaluation-checklist.md`).
5. **Regression Testing** — existing test suite passes at or above prior count (`CLAUDE.md`'s "How to preserve existing behaviour").
6. **Observability** — the change is traceable in production if it affects a traced pipeline stage (`docs/checklists/observability-checklist.md`).
7. **Rollback Plan** — identified and documented before deployment, per the change's applicable `docs/sops/*.md`/`docs/runbooks/*.md`.
8. **Deployment Strategy** — dual-run/shadow/gradual rollout for anything with meaningful blast radius, per the specific migration's own SOP (e.g. `docs/sops/changing-vector-databases.md`).

## Worked examples

Every example below is a real `docs/future/*.md` spec; this policy is what each one's implementation must follow when it's actually built:

- **Qdrant Migration** (`docs/future/QdrantMigration.md`) — ADR already exists (`docs/adr/0020-delay-qdrant-migration.md`, recording the *decision to wait*; the *decision to migrate*, when it happens, needs its own new ADR per this policy). Dual-write/shadow-read deployment strategy specified in the spec itself.
- **Hybrid Retrieval** (`docs/future/HybridRetrieval.md`) — no ADR needed until it's actually built (it's additive to retrieval, not a reversal of an existing decision), but still needs the full Evaluation/Regression/Observability/Rollback steps.
- **Model Replacement** (a real live provider, or `docs/future/ModelRouting.md`) — ADR 0002 already covers the provider-abstraction decision; a specific model swap follows `docs/sops/adding-a-new-llm.md` under this policy's Evaluation/Regression/Rollback requirements without necessarily needing its own new ADR, unless it also changes provider-selection *architecture* (e.g. introducing routing itself, which would warrant one).
- **Embedding Bakeoff** (`docs/future/EmbeddingBakeoff.md`) — the bakeoff itself is a research exercise (no ADR needed); if it results in changing the default provider, that outcome gets its own ADR.
- **Memory V2** (`docs/future/MemoryV2.md`) — needs an ADR before short-term memory ships (it's a genuinely new capability with privacy implications, not an extension of an existing pattern), plus the explicit privacy review this policy's Evaluation step implies for anything touching cross-request context.
- **Knowledge Graph** (`docs/future/KnowledgeGraph.md`) — needs an ADR given its complexity and the schema additions it implies.
- **Continuous Ingestion** (`docs/future/ContinuousIngestion.md`) — builds on the Connector Framework's already-planned architecture (`docs/connectors/connector-framework.md`); needs its own ADR only if its scheduling/job-queue approach introduces new infrastructure beyond what the Connector Framework already specifies.
- **Multimodal** (`docs/future/MultimodalKnowledge.md`) — Phase 1 (OCR/table-to-text) stays inside the existing model, no ADR needed; Phase 2 (native multimodal embeddings, schema additions) needs one.
- **Agent Framework** (`docs/future/AgentFramework.md`) — needs an ADR before any phase ships, given it's the most speculative, highest-blast-radius item in the entire roadmap.
- **Connector Framework** (`docs/future/ConnectorFramework.md`) — needs an ADR before the first connector ships, since it's a genuinely new subsystem (credential storage, external-system auth, sync scheduling) with no existing pattern to extend.

## Enforcement

A major architectural change that ships without a corresponding ADR is treated as a documentation defect requiring immediate remediation (write the ADR retroactively, exactly as `docs/adr/0027` and `docs/adr/0028-engineering-documentation-as-a-first-class-deliverable.md` had to do), not as an acceptable shortcut. `docs/architecture/evolution-policy.md` itself is referenced from `docs/workflows/engineering-lifecycle.md`'s Architecture Review stage so this check happens as part of the normal lifecycle, not as a separate audit.

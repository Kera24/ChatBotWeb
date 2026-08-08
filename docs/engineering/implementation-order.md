# Implementation Order

The exact order future work should be implemented in, and why. This document exists so a future implementer (human or Claude Code) doesn't have to re-derive dependency chains from scratch across two dozen `docs/future/*.md` specs — it's the single place that reasoning is assembled. See `docs/roadmap/roadmap.md` for current status per item and `docs/future/*.md` for each item's full spec.

## Ordering principle

Each step below is justified by: what it depends on (must exist first), the risk of doing it earlier, the expected benefit, and what evaluation is required before it can be considered done. Where two items have no dependency relationship, they're listed in the order of expected benefit-to-risk ratio, not arbitrarily.

## 1. A real (non-mock) AI provider

**Dependencies**: none beyond the existing `AIProvider` interface (`docs/architecture/retrieval.md`).
**Why first**: nearly every subsequent item — model routing, cost optimisation, embedding bake-off, prompt optimisation, agentic features — is either meaningless or unevaluable without real provider behavior. Mock-provider-era evaluation results don't transfer.
**Risk of doing it earlier**: none — this isn't "earlier," it's the actual blocking dependency for most of the rest of the roadmap.
**Expected benefit**: unblocks realistic evaluation, cost accounting, and every provider-dependent future item.
**Evaluation requirement**: full evaluation-gate run against the new provider before any tenant traffic; cost fields (`cost_calc_version`, per-token pricing) must be populated, never left `NULL`-as-zero.

## 2. Continuous evaluation + production feedback loop

**Dependencies**: real provider (#1), stable observability (already shipped).
**Why here**: every subsequent feature listed below benefits from being evaluated against real production-sampled cases, not just the static pre-launch dataset. Building this early means every later item gets a better evaluation signal than it otherwise would.
**Risk of doing it earlier**: low risk either way, but doing it before a real provider exists means "production" traces are still mock-era and less useful as evaluation samples.
**Expected benefit**: regressions in any later feature are caught faster and with real data.
**Evaluation requirement**: verify continuous evaluation catches a deliberately-injected known regression before trusting it for real features.

## 3. Retrieval quality track (Retrieval Optimisation → Hybrid Retrieval → Reranking → Query Rewrite)

**Dependencies**: real provider (#1) for reranking/query-rewrite's own model calls; continuous evaluation (#2) to measure effect reliably.
**Order within this track**: chunking/threshold tuning (`RetrievalOptimisation.md`) first (cheapest, no new infra) → hybrid retrieval (`HybridRetrieval.md`, needs a lexical index) → reranking (`Reranking.md`, needs hybrid's candidate pool) → query rewrite (`QueryRewrite.md`, benefits from but doesn't strictly require memory).
**Why here**: retrieval quality directly affects every downstream answer; improving it before adding more retrieval-consuming features (memory, agentic) compounds the benefit.
**Risk of doing it earlier**: without continuous evaluation, tuning risks overfitting to the static case set.
**Expected benefit**: reduced fallback/evidence-insufficient rate.
**Evaluation requirement**: each sub-item evaluated independently before the next is layered on — no bundling untested changes.

## 4. Short-term memory

**Dependencies**: continuous evaluation (#2) to measure multi-turn effect safely.
**Why here, not earlier**: memory changes context assembly and has privacy implications; it needed a stronger evaluation foundation than pre-launch than the retrieval track above, since multi-turn evaluation cases are qualitatively different from single-question cases.
**Why here, not later**: query rewrite (#3) and eventual agentic features (#8) both benefit from or depend on short-term memory existing — later items would otherwise need to be redesigned once memory is added.
**Risk of doing it earlier**: privacy/scope-boundary mistakes are more likely without a mature evaluation and observability foundation to catch them.
**Expected benefit**: better multi-turn conversation coherence; unblocks query rewrite's context-dependent phase and agentic features.
**Evaluation requirement**: explicit privacy review in addition to the standard evaluation-gate run; multi-turn case set required (doesn't exist yet, must be built as part of this item).

## 5. Connector framework + continuous ingestion

**Dependencies**: none technical (manual ingestion is already stable), but gated on real tenant demand per `docs/adr/0026-manual-ingestion-before-connectors.md`.
**Why here**: independent of the retrieval/memory track above, so it can proceed in parallel once demand is confirmed — there's no technical reason to sequence it strictly after #1-4, only a demand-evidence gate.
**Risk of doing it earlier**: building without confirmed demand risks wasted effort on an unused feature.
**Expected benefit**: unlocks tenants whose knowledge lives outside manually-uploadable files.
**Evaluation requirement**: connector-sourced documents must pass through identical lifecycle/evaluation paths as manual uploads with no special-casing.

## 6. Model routing + cost optimisation

**Dependencies**: a second live provider (beyond #1) for model routing specifically; real cost data (from #1) for cost optimisation generally.
**Why here**: needs more than one provider to have any routing decision to make; cost optimisation benefits from the retrieval/caching work above already having reduced some redundant computation.
**Risk of doing it earlier**: none technical — this is purely dependency-gated on a second provider existing.
**Expected benefit**: reduced per-request cost, better cost/quality tradeoff control.
**Evaluation requirement**: routing strategy must not regress answer quality vs. a single-model baseline.

## 7. Caching V2 / semantic cache

**Dependencies**: observability evidence that redundant computation is a real cost (may already exist by this point given #1-6's traffic growth).
**Why here**: deliberately not earlier — building a cache without evidence risks solving the wrong problem, and semantic caching specifically carries staleness risk that's safer to take on once the rest of the pipeline (memory, retrieval quality) is stable.
**Risk of doing it earlier**: premature caching infrastructure with no measured benefit, plus higher staleness risk if built before document-version-aware invalidation patterns are well understood from the rest of the system.
**Expected benefit**: reduced latency and provider cost.
**Evaluation requirement**: staleness audit (sampled cache hits manually verified) before wide rollout, per `docs/future/SemanticCache.md`.

## 8. Multimodal knowledge, knowledge graph, agentic features

**Dependencies**: multimodal needs a capable provider; knowledge graph needs hybrid retrieval/reranking (#3) mature plus observed multi-hop-question failures; agentic features need memory (#4), model routing (#6), and the most mature possible evaluation/observability foundation.
**Why last**: these are the highest-complexity, most speculative items in the entire roadmap. Each depends on multiple earlier items being genuinely stable, not just shipped.
**Risk of doing it earlier**: highest of any items in this document — building agentic or knowledge-graph capability on an immature foundation (weak evaluation, no memory, no model routing) means rebuilding it later anyway.
**Expected benefit**: qualitatively new capabilities (multi-hop reasoning, autonomous multi-step tasks, richer document types) — but unproven until built, hence the caution.
**Evaluation requirement**: each needs its own dedicated evaluation case set (existing single-turn/single-fact cases don't measure these); agentic features specifically need per-phase opt-in flags, never a default behavior change.

## Independent tracks (not strictly ordered against the above)

- **Deployment/scaling** (`docs/future/DeploymentRoadmap.md`, `docs/future/ScalingRoadmap.md`, `docs/future/DistributedArchitecture.md`, `docs/future/QdrantMigration.md`) — triggered by measured capacity limits, can happen at any point in the sequence above once its own trigger fires. See `docs/engineering/scaling-strategy.md`.
- **Enterprise features** (`docs/future/EnterpriseSSO.md`, `docs/future/ComplianceRoadmap.md`) — triggered by a concrete enterprise-tenant requirement, independent of the technical sequence above.
- **Prompt optimisation / experimentation** (`docs/future/PromptOptimisation.md`) — can proceed alongside #2 (continuous evaluation) once that foundation exists; not strictly gated on #3-8.

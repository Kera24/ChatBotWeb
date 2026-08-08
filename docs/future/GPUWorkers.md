# GPU Workers

## Purpose

Support GPU-backed inference workers, if/when the platform introduces a self-hosted embedding or generation model instead of relying entirely on external provider APIs.

## Current limitation

No self-hosted model inference exists; `MockAIProvider` and (for embeddings) `local-mock`/`ollama` options run on CPU or are external calls — there is no GPU infrastructure in `docker-compose.prod.yml` or `infrastructure/azure/`.

## Why postponed

No self-hosted model requirement exists yet — depends entirely on a future decision to run models locally (for cost, latency, or data-residency reasons), which hasn't been made. Speculative GPU infrastructure without a model to run on it would be pure waste.

## Dependencies

- A concrete decision to self-host a model (cost/latency/data-residency driven), likely tied to `docs/future/CostOptimisation.md` or `docs/future/ComplianceRoadmap.md`'s data-residency requirements.
- `docs/future/DeploymentRoadmap.md`'s scaling triggers, since GPU workers are a capacity-tier decision.

## Implementation phases

1. Identify the specific driver (cost savings at scale, data residency, latency) that justifies self-hosting a model, with numbers.
2. Provision a GPU-capable worker (VPS GPU instance or Azure GPU-enabled Container Apps/VM) as an additive worker pool, not a replacement for the existing provider abstraction.
3. Register the self-hosted model through the existing `ProviderRegistry`/`ModelRegistry` (`docs/architecture/retrieval.md`) — no orchestrator special-casing.
4. A/B against the existing external-provider path on cost, latency, and evaluation quality before making it a default.

## Technical design

A new `AIProvider` implementation calling a locally-hosted inference server (e.g. vLLM/Ollama-style), fitting the existing provider abstraction exactly — the RAG pipeline doesn't need to know whether a provider is local or remote.

## Evaluation plan

Cost-per-request and latency comparison against the external-provider baseline, plus full evaluation-gate parity (self-hosted model must not regress answer quality) before adoption.

## Rollback strategy

Provider-abstraction-based: falling back to the external provider is a config change (`ProviderRegistry` selection), not an architectural rollback.

## Success metrics

Demonstrated cost or latency improvement (matching the original driver) with no evaluation-gate regression.

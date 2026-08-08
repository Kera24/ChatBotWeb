# Runbook: Embedding Service Failure

## Symptoms

Ingestion pipeline stuck at the embedding step (`DocumentVersion.processing_status` not advancing), or query-time retrieval failing at the embed-query step.

## Diagnosis

1. Check `build_embedding_provider()`'s configured provider (`EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`) — is it reachable (network, auth, quota)?
2. Check `DocumentVersion.processing_error` for the specific failure message on stuck documents.
3. Determine if this is ingestion-side only, query-side only, or both (they use the same provider but are different call sites).

## Recovery

1. If the embedding provider (e.g. Ollama, external API) is down: this blocks both ingestion and retrieval — treat as a high-severity outage.
2. Once the provider recovers, stuck `DocumentVersion` rows need to be re-processed — never mark them `ready` without actually re-running the embedding step (per `document_lifecycle`'s "invalid transitions raise" invariant, this shouldn't be bypassable, but confirm no manual DB edit was attempted).
3. If query-time embedding fails, requests correctly fail loud (per `docs/architecture/knowledge-ingestion.md`'s "no embedding fallback strategy" documented current state) — confirm users see a clear error, not a silent bad answer.

## Validation

New documents process to `ready` successfully; query-time retrieval succeeds again; no document stuck in a partial state.

## Escalation

If the provider is self-hosted (Ollama) and the VPS itself is the bottleneck, escalate per `docs/runbooks/vps-recovery.md`.

## Post-incident review

Consider whether `docs/future/EmbeddingBakeoff.md`'s eventual multi-provider work should include a fallback strategy — currently explicitly out of scope until then.

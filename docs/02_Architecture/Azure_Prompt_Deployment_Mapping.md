# Azure Prompt Deployment Mapping

Status: reference document - this platform currently deploys to a low-cost VPS (see `docs/architecture/deployment.md`); this document maps the prompt-management feature onto Azure for a future migration, and is not itself a deployment guide. Mirrors the structure of `Azure_Monitor_Application_Insights_Mapping.md`.

## Why this mapping matters

Prompt management (`docs/architecture/prompts.md`) is entirely Postgres-backed application data plus in-process resolution logic — it has no VPS-specific or cloud-specific dependency today. This document exists so a future Azure migration doesn't need to re-derive which pieces are infrastructure-agnostic versus which would benefit from an Azure-native equivalent.

## Component mapping

| Today | Azure equivalent | Notes |
|---|---|---|
| `prompt_templates`/`prompt_versions`/`prompt_deployments`/`prompt_experiments`/`prompt_audit_events` (Postgres tables) | Unchanged. | Application data - migrates with the rest of the database regardless of which cloud/VPS the API runs on. |
| `app.prompts.resolution`'s in-process 30-second deployment cache | Unchanged, or optionally Azure Cache for Redis if the API scales to multiple instances. | The current cache is per-process; on a single VPS instance this is fine. If a future Azure deployment runs multiple API replicas, each replica's own 30-second cache means a deploy/rollback can take up to 30s to reach *some* replicas even after `invalidate_cache()` runs on the replica that handled the write - a shared cache (or a pub/sub invalidation broadcast) would close that gap. Not needed at current single-instance VPS scale. |
| `app.operations.prompt_promote` CLI | Azure DevOps / GitHub Actions pipeline step, same as `eval_release_gate_check.py`'s existing CI wiring. | No code change - just an additional pipeline step running the same CLI against the Azure-hosted database. |
| Prompt-version-tagged AI traces (`AIModelCallTrace.resolved_layer_version_ids`, `.experiment_id`, `.experiment_arm`) | Application Insights custom dimensions, following the same pattern as the rest of `AI_Observability_Architecture.md`'s Azure mapping. | These columns are queried the same way regardless of backend (Postgres `ai_model_call_traces` table); an Azure migration would additionally want them surfaced as custom dimensions on the corresponding Application Insights dependency/request telemetry for cross-correlation, matching how `otel_trace_id`/`otel_span_id` already bridge the two systems. |
| Experiment metrics (`app.prompts.experiment_metrics`) | Unchanged, or an Azure Monitor Workbook panel. | Currently a direct SQL aggregation exposed via `GET .../prompts/experiments/{id}/metrics`; a future workbook panel would be a straightforward KQL port once trace data also flows through Application Insights. |

## What does NOT change on an Azure migration

The entire prompt-management data model, the rendering bridge (`app.prompts.resolution`), the promotion gate (`app.evaluation.prompt_promotion_gate`), RBAC, and tenant isolation are all infrastructure-agnostic — they read/write Postgres and call the existing (also infrastructure-agnostic) evaluation engine. None of this feature's code paths know or care which cloud, if any, the process runs on.

## What DOES change

- If the API scales to multiple replicas on Azure App Service / AKS, revisit the per-process deployment cache (see the table above) - either accept the up-to-30-second cross-replica propagation delay, or add a shared invalidation mechanism.
- Prompt-version identity fields become additionally queryable as Application Insights custom dimensions once the OTel-to-Azure-Monitor bridge is active (see `Azure_Monitor_Application_Insights_Mapping.md`), for cross-referencing "which prompt version was active during this incident" directly in the Azure trace UI rather than joining back to Postgres.

## Non-goals of this mapping

This document does not perform a migration, provision Azure resources, or change any code.

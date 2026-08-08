# Prompt Rollback Runbook

See `docs/architecture/prompts.md` for the data model. This is the operational procedure for rolling a `PromptDeployment` back to its previous version.

## When to roll back

A newly-deployed prompt version is causing a measurable quality or safety regression (elevated fallback rate, guardrail-trigger rate, citation-coverage drop, or a direct report of incorrect/unsafe behaviour) and the fix cannot wait for a new version to be drafted, evaluated, approved, and deployed through the normal flow.

## Procedure

1. **Identify the deployment.** `GET /api/v1/workspaces/{workspace_id}/prompts/deployments?organisation_id=...&layer=<layer>&widget_id=<widget_id or omit for platform_core>` — note the `id` (the deployment) and `active_version_id` (the version currently causing the problem).
2. **Roll back.** `POST /api/v1/workspaces/{workspace_id}/prompts/deployments/{deployment_id}/rollback?organisation_id=...` with an optional `{"reason": "..."}` body. This requires `org_owner`/`client_admin` for workspace-scoped layers, or `super_admin` for the platform-immutable `platform_core` layer (rollback follows the same RBAC split as deploy — see `docs/03_AI/Prompt_Layering_and_Security_Policy.md`).
3. **Verify.** Re-fetch the deployment (step 1) and confirm `active_version_id` now matches the previous known-good version. `GET /api/v1/workspaces/{workspace_id}/prompts/preview?organisation_id=...&widget_id=<widget_id>` shows the actual rendered composite prompt now in effect.
4. **Check the audit trail.** `GET /api/v1/workspaces/{workspace_id}/prompts/audit-events?organisation_id=...&entity_id=<deployment_id>` — a `rolled_back` event should be present with your reason attached.

## What rollback does and does not do

- **Immediate**: `app.prompts.resolution.invalidate_cache(widget_id)` is called synchronously as part of `rollback_deployment()` — the next request for that scope resolves the restored version, not the up-to-30-second-stale cached one.
- **Never deletes**: the failed version's row is preserved (its `status` becomes `rolled_back`, not removed) — it stays fully inspectable via `GET .../prompts/versions/{id}` for post-incident review, and can be re-deployed later if the "regression" turns out to be a false alarm.
- **A second rollback swaps back**: `PromptDeployment.previous_version_id` is never `None` after a deployment has been rolled over at least once, so calling rollback again on the same deployment restores the version you just rolled back *from* — this is intended ("undo the undo"), not an error. `rollback_deployment()` only raises `NoRollbackTarget` when the deployment has genuinely never had a second version deployed to it.
- **Active conversations**: per-request prompt resolution happens fresh on every `RAGOrchestrator.answer()` call — there is no per-conversation prompt pinning, so an in-progress conversation's *next* turn uses the rolled-back version immediately; nothing about the turn already answered is retroactively changed.
- **Release gate**: if a future release-gate check needs to verify a specific version is the active one before proceeding, query the deployment endpoint (step 1) directly — there is no separate CLI for this today; `app.operations.prompt_promote` checks candidate *evaluation* readiness, not current deployment state.

## Rollback within an active experiment

If a `PromptExperiment` is running against the same layer/widget at the time of an incident, kill the experiment first (`POST .../prompts/experiments/{id}/kill`) so the experiment's own arm-override logic doesn't immediately re-serve the candidate to its assigned traffic share after you roll the deployment back — see `docs/04_Engineering/Prompt_Experiment_Guide.md`'s kill-switch section (checked live, no caching, takes effect on the next request).

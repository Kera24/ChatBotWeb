# Future Azure Scheduled-Evaluation Mapping

Related: [Future Azure Migration Notes](./Future_Azure_Migration_Notes.md), [Nightly Evaluation VPS Guide](./Nightly_Evaluation_VPS_Guide.md).

The production feedback loop's scheduled CLIs (`production_signal_scan`, `eval_focused_run`, `eval_regression_report`, `eval_release_gate_check`) are plain Python, invoked via `python -m app.operations.<module>`, reading `SessionLocal`/env config exactly like every other `app.operations.eval_*` CLI already in this codebase. They have **no VPS-only dependency** — cron/systemd on the VPS today, an Azure job runner later, same command either way.

## Mapping

| VPS today | Azure equivalent | Notes |
|---|---|---|
| cron/systemd timer running `npm run feedback:scan -- ...` | Azure Container Apps Job (scheduled trigger) or a Functions Timer Trigger | Same command; `modules/migration-job.bicep` is the existing precedent for "Container Apps Job running a one-shot `app.operations.*` script" (see [Future Azure Migration Notes](./Future_Azure_Migration_Notes.md) item 5) — a new `modules/feedback-loop-jobs.bicep` (not yet written) would follow the identical shape, one job definition per CLI, parameterised by `--organisation/--workspace/--assistant`. |
| Cron log file (`/var/log/conversa/*.log`) | Azure Monitor / Application Insights log stream | Flip `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` (already wired, inert on the VPS today, see `app/operations/telemetry.py`) — CLI stdout/stderr becomes queryable the same way any other container's logs do. |
| `scripts/release-gate.mjs`'s optional `--feedback-loop-*` step | `scripts/validate-production-pilot-readiness.mjs`'s Azure-specific equivalent gate | Same `eval_release_gate_check` CLI underneath; only the wrapper script differs, matching the existing VPS-vs-Azure release-gate split (see [Future Azure Migration Notes](./Future_Azure_Migration_Notes.md) item 7). |
| Manual per-assistant CLI invocation | A parameterised job triggered per assistant (e.g. by a small orchestrator reading the assistant list from the DB) | Not built on either target today — both the VPS and Azure paths currently require an operator (or a cron entry) to name the assistant explicitly. Building fleet-wide enumeration is future work independent of the deployment target. |

## What would need to change

Nothing in the application code. `EvaluationCandidate`/`EvaluationDatasetVersionEvent`/`EvaluationRegressionReport` are ordinary tables migrated by the same Alembic chain Azure already runs via its migration job. The only new work for an Azure rollout is infrastructure-as-code (job/timer definitions) and wiring the existing `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED` flag — no new environment variables, no new secrets, no schema changes beyond what's already in `0018_production_feedback_loop.py`.

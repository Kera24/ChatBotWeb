# Nightly Evaluation VPS Guide

Goal: run the production feedback loop's scan/focused-eval/regression-report/release-gate CLIs on a schedule against the single-VPS deployment, without a managed job scheduler. Same pattern as `deployment/monitoring/check.sh` — external cron/systemd timer, no new Compose service (`docker-compose.prod.yml` is off-limits without explicit instruction).

## Commands

All one-shot CLIs, `npm run <script> -- <flags>` (or `python -m app.operations.<module> <flags>` directly inside the `api` container). Every one requires an explicit `--organisation`/`--workspace`/`--assistant`, matching every other `eval_*` CLI in this codebase — a fleet-wide job loops per assistant rather than the CLI enumerating tenants itself.

| Command | Purpose | Exit codes |
|---|---|---|
| `npm run feedback:scan -- --organisation <id> --workspace <id> --assistant <id> [--since-hours 24] [--dry-run]` | Scan recent production traffic for failure signals, create/bump `EvaluationCandidate` rows | 0 success, 2 operational error |
| `npm run eval:focused -- --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--since-run <run_id>]` | Run only production-fed cases (defaults to all `source_candidate_id`-set cases; `--since-run` narrows to cases added after a baseline run) | 0 on run completion, 2 operational error |
| `npm run eval:regression-report -- --run <run_id> --baseline-run <run_id> --organisation <id> --workspace <id> [--created-by system:nightly] [--gate]` | Classify new/fixed/newly-failing cases between two runs, persist an `EvaluationRegressionReport` | 0 always unless `--gate` and the verdict fails (then 1), 2 operational error |
| `npm run eval:release-gate-check -- --dataset <id> --assistant <id> --organisation <id> --workspace <id> [--max-baseline-age-days 7]` | Production feedback loop release gate (see `docs/06_Operations/Regression_Release_Policy.md`) | 0 pass, 1 fail, 2 operational error |

## Cadence

- **Nightly** (per assistant): `feedback:scan` (window `--since-hours 24`), then — if it created or bumped any candidates worth acting on — nothing else automatic; scanning only populates the triage queue, it never promotes anything.
- **After every accepted-candidate promotion**: run `eval:focused` against the dataset the candidate was promoted into, to confirm the new case reproduces/is fixed, then `eval:regression-report` against the previous full-dataset baseline run.
- **Weekly**: a full-dataset `eval:run` (existing CLI, unchanged) as the "weekly full regression" baseline referenced by the release gate's staleness check.

## Cron example

```cron
# Nightly signal scan for one assistant at 02:00 server time
0 2 * * * conversa cd /home/conversa/app && npm run feedback:scan -- --organisation org_xxx --workspace ws_xxx --assistant asst_xxx >> /var/log/conversa/feedback-scan.log 2>&1

# Weekly full regression + release-gate check, Sunday 03:00
0 3 * * 0 conversa cd /home/conversa/app && npm run eval:run -- --dataset ds_xxx --assistant asst_xxx --organisation org_xxx --workspace ws_xxx --format json > /tmp/weekly-run.json && npm run eval:release-gate-check -- --dataset ds_xxx --assistant asst_xxx --organisation org_xxx --workspace ws_xxx >> /var/log/conversa/release-gate.log 2>&1
```

## systemd timer alternative

Same pattern as any other scheduled task on this VPS — a `.service` unit running the `npm run <script>` command with `WorkingDirectory=/home/conversa/app`, paired with a `.timer` unit (`OnCalendar=*-*-* 02:00:00`). No example unit files are checked in yet; copy the structure of whatever timer units already exist for `backup.sh` if any, or write a minimal `[Service] Type=oneshot ExecStart=...` unit.

## Future Azure mapping

See `docs/06_Operations/Future_Azure_Scheduled_Evaluation_Mapping.md` — these CLIs are deployment-agnostic (plain Python, read `SessionLocal`/env config) and map directly onto an Azure Container Apps Job or Functions Timer Trigger without code changes, once that migration happens.

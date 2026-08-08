# Runbook: Backup Restore

## Symptoms

Not itself an incident — this is the procedure invoked by `docs/runbooks/database-recovery.md`, `docs/runbooks/vps-recovery.md`, or a deliberate restore drill.

## Diagnosis

Confirm which backup to restore from (`$BACKUP_DIR/postgres/`, dated `pg_dump | gzip -9` archives) and the `uploads_data` volume tar — verify the backup's age against the incident's data-loss window.

## Recovery

1. Run `deployment/backup/restore.sh` with explicit `--db`/`--uploads` paths.
2. Confirm interactively (or pass `--yes` if this is a scripted/automated drill) — the script terminates connections, drops/recreates the DB, replays the dump, and wipes/restores the uploads volume. This is destructive to current state — never run against a database you haven't confirmed is the one that needs restoring.
3. Run `database_migration preflight` immediately after restore.

## Validation

Application starts cleanly against the restored data; spot-check known recent records exist and are correct; migration preflight clean.

## Escalation

If the restore itself fails or produces inconsistent data, escalate — do not attempt a second destructive restore without understanding why the first failed.

## Post-incident review

If this was a real recovery (not a drill): how much data was lost relative to the backup's age? If this was a scheduled drill: did it complete within the expected time/effort, and did it reveal any gap in the backup/restore scripts?

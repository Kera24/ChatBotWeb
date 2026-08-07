# Backup and Restore Runbook

Scripts: `deployment/backup/backup.sh`, `deployment/backup/restore.sh`.
**This runbook's restore procedure has been executed end-to-end against a
real (isolated) instance of `docker-compose.prod.yml` with synthetic data as
part of this launch audit** - inserted a synthetic organisation row, took a
backup, deleted the row, restored from the backup, and confirmed the row
came back. See the launch report's Backup/Restore section for the drill log.

## What gets backed up

1. **Postgres** - full logical dump via `pg_dump` (plain SQL, gzip-compressed) of the database named in `POSTGRES_DB`.
2. **Uploaded documents** - a tar.gz snapshot of the `uploads_data` Docker volume (`LOCAL_UPLOAD_ROOT`'s backing store).

Both are written under `BACKUP_DIR` (default `./backups` at the repo root on
the VPS), with a UTC timestamp in the filename, so successive runs never
overwrite each other.

## Running a backup manually

```bash
./deployment/backup/backup.sh
# or: npm run vps:backup
```

Non-zero exit code = backup failed (either step). Wire this into monitoring
(see [Monitoring_Runbook.md](./Monitoring_Runbook.md)) rather than assuming
cron ran successfully.

## Scheduling - cron

```cron
# /etc/cron.d/conversa-backup
0 3 * * * conversa cd /home/conversa/app && ./deployment/backup/backup.sh >> /var/log/conversa-backup.log 2>&1
```

## Scheduling - systemd timer (preferred - gives you `systemctl status`, journal logs, and failure alerting for free)

```ini
# /etc/systemd/system/conversa-backup.service
[Unit]
Description=Conversa Postgres + uploads backup

[Service]
Type=oneshot
WorkingDirectory=/home/conversa/app
ExecStart=/home/conversa/app/deployment/backup/backup.sh
User=conversa
```

```ini
# /etc/systemd/system/conversa-backup.timer
[Unit]
Description=Run Conversa backup daily

[Timer]
OnCalendar=03:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now conversa-backup.timer
systemctl list-timers conversa-backup.timer
```

A failed run shows up in `systemctl status conversa-backup.service` and
`journalctl -u conversa-backup.service` - point your alerting at
`OnFailure=` in the service unit (e.g. a unit that pings a dead-man's-switch
/healthcheck.io style URL) if you want proactive failure alerts rather than
checking manually.

## Retention

`backup.sh` deletes local `*.sql.gz`/`*.tar.gz` files older than
`RETENTION_DAYS` (default 14) on every run. This bounds local disk usage but
is **not** a substitute for offsite backup - a lost/destroyed VPS takes the
retained backups with it.

## Offsite / encrypted backup (recommended, not automated here)

Copy `BACKUP_DIR` off the VPS on a schedule, encrypted in transit and at
rest. Two low-cost options, neither requires new infrastructure-as-code:

- `rclone sync --transfers 4 <BACKUP_DIR> remote:conversa-backups` to any
  S3-compatible/object storage bucket with server-side encryption enabled.
- `restic` (built-in encryption + deduplication + retention policies) backing
  onto the same kind of bucket: `restic backup <BACKUP_DIR>`.

Either can be added as a second cron job/systemd timer that runs shortly
after the local backup job.

## Disk-space monitoring

`backup.sh` prints a `WARNING` to stderr if free space at `BACKUP_DIR` drops
below `DISK_WARN_MB` (default 2048, i.e. 2GB). `deployment/monitoring/check.sh`
performs the same check against the repo root's filesystem on every
monitoring run, independent of when backups run.

## Restore procedure

**This overwrites the target database/volume - never run it against a live
database you don't intend to replace, without confirming the target first.**

```bash
# Database only:
./deployment/backup/restore.sh --db backups/postgres/conversa-<timestamp>.sql.gz

# Database + uploaded documents:
./deployment/backup/restore.sh \
  --db backups/postgres/conversa-<timestamp>.sql.gz \
  --uploads backups/uploads/uploads-<timestamp>.tar.gz

# Non-interactive (e.g. from an automated DR runbook):
./deployment/backup/restore.sh --db <path> --yes
```

The script terminates other connections to the target database, drops and
recreates it, then replays the dump with `ON_ERROR_STOP=1` (fails loudly
instead of silently skipping broken statements).

## Restore validation

After any restore:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec api \
  python -m app.operations.database_migration preflight
docker compose -f docker-compose.prod.yml --env-file .env.production restart api web
curl -s https://<API_DOMAIN>/health/ready
```

Then spot-check the restored data through the product itself (log in, open
an assistant, confirm a known conversation/document is present) - a
successful SQL replay does not by itself prove the application-level data is
coherent.

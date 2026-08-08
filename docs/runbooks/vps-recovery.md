# Runbook: VPS Recovery

## Symptoms

Host-level failure: disk full, out of memory, network unreachable, or the VPS itself unresponsive.

## Diagnosis

1. Check disk usage first (`deployment/backup/backup.sh`'s low-disk warning should have caught this proactively — if it didn't, that's a gap to close).
2. Check memory/CPU via host-level monitoring (or `docker stats` if the host is still reachable).
3. If network-unreachable: contact the VPS provider for host-level status.

## Recovery

1. Disk full: clear old backups beyond retention (`deployment/backup/`'s `find -mtime +N -delete` should already do this — verify it ran), clear unused Docker images/volumes.
2. Out of memory: identify the runaway container (`docker stats`), restart it; if recurring, this may be a `docs/engineering/scaling-strategy.md` trigger (vertical scaling needed).
3. Full host failure: restore from backup onto a new VPS instance per `docs/runbooks/backup-restore.md`, repoint DNS.

## Validation

Host resources back to healthy levels; all services running; smoke checks pass.

## Escalation

A full host-loss recovery is a major incident — escalate immediately and consider whether this event alone justifies revisiting `docs/adr/0027-vps-first-controlled-pilot-hosting.md`'s risk tradeoffs (single point of failure vs. Azure's managed redundancy).

## Post-incident review

Was backup/restore actually tested recently, or only assumed to work? This incident is the real-world test — document how long recovery took.

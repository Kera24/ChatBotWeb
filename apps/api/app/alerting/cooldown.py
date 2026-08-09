from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from app.operations.logging import log_operational_event

logger = logging.getLogger("app.alerting.cooldown")


class AlertCooldownStore:
    """Tracks the last-delivered timestamp per dedup key in a small JSON
    file on disk. Deliberately not a database table (no schema migration
    needed for this pass) or a Redis-backed store (the alert-delivery CLI
    has no other dependency on Redis being reachable) - a local state file
    matches this project's single-VPS-first deployment philosophy (see
    docs/architecture/deployment.md) and is trivially readable/resettable
    from a systemd timer/cron context.

    Corrupt or missing state is treated as "no prior delivery" rather than
    raising - a cooldown miss (one extra notification) is far cheaper than
    crashing the alert-delivery CLI over a state-file read error."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def last_delivered_at(self, dedup_key: str) -> datetime | None:
        raw = self._read().get(dedup_key)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def is_in_cooldown(self, dedup_key: str, *, cooldown_seconds: int, now: datetime) -> bool:
        if cooldown_seconds <= 0:
            return False
        last = self.last_delivered_at(dedup_key)
        if last is None:
            return False
        return (now - last).total_seconds() < cooldown_seconds

    def record_delivery(self, dedup_key: str, *, now: datetime) -> None:
        state = self._read()
        state[dedup_key] = now.isoformat()
        self._write(state)

    def _read(self) -> dict[str, str]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (ValueError, OSError):
            log_operational_event(logger, {"event": "alert.cooldown_store.read_failed", "path": str(self._path)})
            return {}

    def _write(self, state: dict[str, str]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            log_operational_event(logger, {"event": "alert.cooldown_store.write_failed", "path": str(self._path)})

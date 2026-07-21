from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PublicUsageSnapshot:
    daily_message_count: int | None = None
    daily_token_usage: int | None = None
    daily_estimated_cost: Decimal | None = None
    degraded: bool = False


class PublicUsageRepository(Protocol):
    def snapshot_for_workspace(self, *, organisation_id: str, workspace_id: str, day: date) -> PublicUsageSnapshot:
        ...


class InMemoryPublicUsageRepository:
    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str, date], PublicUsageSnapshot] = {}

    def set_snapshot(self, *, organisation_id: str, workspace_id: str, day: date, snapshot: PublicUsageSnapshot) -> None:
        self._snapshots[(organisation_id, workspace_id, day)] = snapshot

    def snapshot_for_workspace(self, *, organisation_id: str, workspace_id: str, day: date) -> PublicUsageSnapshot:
        return self._snapshots.get((organisation_id, workspace_id, day), PublicUsageSnapshot())

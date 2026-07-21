from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class InMemoryOperationalMetrics:
    counters: Counter[str] = field(default_factory=Counter)

    def increment(self, name: str, *, status: str = "total") -> None:
        self.counters[f"{name}.{status}"] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self.counters)


def metric_name_for_event(event_type: str) -> tuple[str, str]:
    parts = event_type.split(".")
    if len(parts) < 3 or parts[0] != "widget":
        return "public_widget.event", "total"
    route = parts[1]
    action = parts[2]
    if action in {"served", "created", "accepted", "response_projected", "not_modified"}:
        return f"public_widget.{route}", "success"
    if action in {"rejected", "origin_denied", "unavailable", "rate_limited"}:
        return f"public_widget.{route}", action
    if action in {"fallback", "duplicate"}:
        return f"public_widget.{route}", action
    return f"public_widget.{route}", "total"


"""Test helpers for discovering FastAPI routes without assuming every app.routes entry is a concrete route."""

from collections.abc import Iterable
from typing import Any


def route_paths(routes: Iterable[Any]) -> set[str]:
    """Return concrete route paths and ignore router sentinels or non-route entries."""
    return {path for route in routes if isinstance((path := getattr(route, "path", None)), str)}

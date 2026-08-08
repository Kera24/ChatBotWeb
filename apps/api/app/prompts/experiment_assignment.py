"""Deterministic, stable traffic-split assignment for prompt experiments.
Assignment is a pure function of (experiment_id, unit_key) - the same
conversation always lands on the same arm for the lifetime of the experiment,
and no state needs to be persisted to make that true."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from app.db.models.prompt import PromptExperiment

ARM_CONTROL = "control"
ARM_CANDIDATE = "candidate"


def is_experiment_live(experiment: PromptExperiment, *, now: datetime | None = None) -> bool:
    """The kill switch (status != "running") and the max-duration window
    (end_at) are both checked live, with no caching, so flipping either takes
    effect on the very next request - see app.prompts.resolution's cache,
    which caches deployment/version lookups but never the experiment's own
    status check."""
    if experiment.status != "running":
        return False
    now = now or datetime.now(timezone.utc)
    start_at = _as_aware(experiment.start_at)
    end_at = _as_aware(experiment.end_at)
    if start_at is not None and now < start_at:
        return False
    if end_at is not None and now > end_at:
        return False
    return True


def assign_arm(experiment: PromptExperiment, unit_key: str) -> str:
    """Stable hash-based bucketing: sha256(experiment_id:unit_key) mod 100,
    compared against traffic_allocation_percentage (the candidate's share).
    `unit_key` should be a conversation id where available (stable across
    turns in one conversation) - see app.prompts.resolution."""
    digest = sha256(f"{experiment.id}:{unit_key}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return ARM_CANDIDATE if bucket < experiment.traffic_allocation_percentage else ARM_CONTROL


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

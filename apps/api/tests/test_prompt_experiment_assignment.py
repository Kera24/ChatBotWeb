from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models.prompt import PromptExperiment
from app.prompts.experiment_assignment import ARM_CANDIDATE, ARM_CONTROL, assign_arm, is_experiment_live


def _experiment(**overrides) -> PromptExperiment:
    defaults = dict(
        id="exp-1", organisation_id="org-1", workspace_id="ws-1", widget_id="widget-1", layer="assistant_persona_tone",
        control_version_id="v-control", candidate_version_id="v-candidate", traffic_allocation_percentage=50,
        status="running", start_at=None, end_at=None, max_duration_hours=None, safety_gate_state="passed",
    )
    defaults.update(overrides)
    return PromptExperiment(**defaults)


def test_assignment_is_deterministic_for_the_same_unit_key() -> None:
    experiment = _experiment()
    first = assign_arm(experiment, "conversation-abc")
    second = assign_arm(experiment, "conversation-abc")
    assert first == second


def test_assignment_distributes_across_arms_over_many_units() -> None:
    experiment = _experiment(traffic_allocation_percentage=50)
    arms = {assign_arm(experiment, f"conversation-{i}") for i in range(200)}
    assert arms == {ARM_CONTROL, ARM_CANDIDATE}


def test_zero_allocation_never_assigns_candidate() -> None:
    experiment = _experiment(traffic_allocation_percentage=0)
    for i in range(50):
        assert assign_arm(experiment, f"conversation-{i}") == ARM_CONTROL


def test_full_allocation_always_assigns_candidate() -> None:
    experiment = _experiment(traffic_allocation_percentage=100)
    for i in range(50):
        assert assign_arm(experiment, f"conversation-{i}") == ARM_CANDIDATE


def test_kill_switch_takes_effect_immediately() -> None:
    experiment = _experiment(status="running")
    assert is_experiment_live(experiment) is True
    experiment.status = "killed"
    assert is_experiment_live(experiment) is False


def test_experiment_outside_its_time_window_is_not_live() -> None:
    now = datetime.now(timezone.utc)
    not_started_yet = _experiment(start_at=now + timedelta(hours=1))
    assert is_experiment_live(not_started_yet, now=now) is False

    already_ended = _experiment(end_at=now - timedelta(hours=1))
    assert is_experiment_live(already_ended, now=now) is False

    currently_running = _experiment(start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1))
    assert is_experiment_live(currently_running, now=now) is True


def test_non_running_status_is_never_live() -> None:
    for status in ("draft", "paused", "completed", "killed"):
        assert is_experiment_live(_experiment(status=status)) is False

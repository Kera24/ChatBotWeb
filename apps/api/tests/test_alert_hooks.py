"""Tests for app.alerting.hooks.notify_gate_failure - the fail-safe dispatch
helper wired into app.operations.eval_release_gate_check and
eval_regression_report for the "evaluation gate failure" / "prompt
regression" / "deployment release-gate failure" alert categories. Must never
raise, even when the configured alert provider is misconfigured, since these
CLIs' existing stdout/exit-code contracts (see test_eval_release_gate_check.py,
test_eval_regression_report.py) must stay unaffected."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from app.alerting.hooks import notify_gate_failure
from app.core.config import settings


@contextmanager
def _settings_override(**overrides: Any) -> Iterator[None]:
    originals = {name: getattr(settings, name) for name in overrides}
    for name, value in overrides.items():
        object.__setattr__(settings, name, value)
    try:
        yield
    finally:
        for name, value in originals.items():
            object.__setattr__(settings, name, value)


@contextmanager
def _capture_logger(name: str) -> Iterator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(name)
    handler = _ListHandler()
    original_level = logger.level
    original_disabled = logger.disabled
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.disabled = original_disabled


def test_notify_gate_failure_dispatches_via_dev_provider(tmp_path) -> None:
    with _settings_override(ALERT_PROVIDER="dev", ALERT_MIN_SEVERITY="info", ALERT_COOLDOWN_STATE_PATH=str(tmp_path / "cooldown.json")):
        with _capture_logger("app.alerting.providers.dev") as records:
            notify_gate_failure(
                alert_key="evaluation_release_gate_failed",
                category="evaluation_gate_failure",
                message="Production release gate failed for dataset ds-1: hard failure(s) present",
                source_subsystem="evaluation_release_gate",
                organisation_id="org-1",
                workspace_id="ws-1",
                assistant_id="asst-1",
                correlation_id="ds-1",
            )

    [record] = records
    payload = json.loads(record.getMessage())
    assert payload["alert_key"] == "evaluation_release_gate_failed"
    assert payload["severity"] == "critical"


def test_notify_gate_failure_never_raises_when_provider_is_misconfigured(tmp_path) -> None:
    with _settings_override(ALERT_PROVIDER="slack", SLACK_WEBHOOK_URL="", ALERT_COOLDOWN_STATE_PATH=str(tmp_path / "cooldown.json")):
        # Must not raise - a misconfigured alert provider must never affect
        # the CLI call site's own exit code or output.
        notify_gate_failure(
            alert_key="evaluation_regression_detected",
            category="prompt_regression",
            message="Regression detected",
            source_subsystem="evaluation_regression",
            organisation_id="org-1",
            workspace_id="ws-1",
        )


def test_notify_gate_failure_never_raises_when_provider_deliver_explodes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.alerting import hooks as hooks_module

    def _explode() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hooks_module, "build_alert_provider", _explode)
    with _settings_override(ALERT_COOLDOWN_STATE_PATH=str(tmp_path / "cooldown.json")):
        notify_gate_failure(
            alert_key="evaluation_release_gate_failed",
            category="evaluation_gate_failure",
            message="Production release gate failed",
            source_subsystem="evaluation_release_gate",
            organisation_id="org-1",
            workspace_id="ws-1",
        )

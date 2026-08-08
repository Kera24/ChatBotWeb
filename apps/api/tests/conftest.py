"""Shared pytest configuration for apps/api/tests.

The suite's existing test fixtures authenticate almost every request via the
X-Development-User-Email/X-Development-Role headers (see
app.api.deps.get_development_current_user). As of the P1-2 launch-readiness
fix, that path additionally requires settings.ALLOW_DEV_AUTH=true (APP_ENV
being development/test/testing is no longer sufficient on its own) - this
autouse fixture is the "test configuration/fixtures explicitly enabling the
flag" called for by that fix, rather than weakening the new default-off
policy itself. Individual tests that need to exercise the flag disabled/in a
production-like environment override it explicitly via their own
_settings_override context manager (see tests/test_dev_auth_policy.py).
"""

from __future__ import annotations

from typing import Iterator

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _allow_dev_auth_in_tests() -> Iterator[None]:
    original = settings.ALLOW_DEV_AUTH
    object.__setattr__(settings, "ALLOW_DEV_AUTH", True)
    try:
        yield
    finally:
        object.__setattr__(settings, "ALLOW_DEV_AUTH", original)

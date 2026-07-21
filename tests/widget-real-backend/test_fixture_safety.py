from __future__ import annotations

import pytest

from conftest import assert_safe_real_backend_environment


def test_safety_guard_requires_explicit_synthetic_test_flag() -> None:
    with pytest.raises(RuntimeError, match="WIDGET_REAL_BACKEND_TEST"):
        assert_safe_real_backend_environment({"APP_ENV": "test"}, database_url="sqlite+pysqlite:///:memory:")


def test_safety_guard_rejects_production_like_database() -> None:
    env = {"APP_ENV": "test", "WIDGET_REAL_BACKEND_TEST": "1"}

    with pytest.raises(RuntimeError, match="production-like"):
        assert_safe_real_backend_environment(env, database_url="postgresql://user:pass@prod-db.example/yoranix")

    with pytest.raises(RuntimeError, match="production-like"):
        assert_safe_real_backend_environment(env, database_url="sqlite:///customer-production.db")


def test_safety_guard_accepts_isolated_sqlite_test_context() -> None:
    assert_safe_real_backend_environment({"APP_ENV": "test", "WIDGET_REAL_BACKEND_TEST": "1"}, database_url="sqlite+pysqlite:///:memory:")

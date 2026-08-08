"""Tests for the development-header auth fail-closed policy (P1-2 of the
launch readiness review): app.api.deps.get_development_current_user must
only trust X-Development-User-Email/X-Development-Role when BOTH APP_ENV is
development/test/testing AND settings.ALLOW_DEV_AUTH is explicitly enabled,
and app.api.deps.assert_dev_auth_policy_safe must refuse to boot on an
unsafe APP_ENV=production + ALLOW_DEV_AUTH=true combination. Uses the same
_settings_override pattern as test_ai_provider_selection.py/
test_email_provider.py to mutate the frozen Settings singleton for the
duration of a test."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import assert_dev_auth_policy_safe
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


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


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def dev_headers(email: str = "super@example.test", role: str = "super_admin") -> dict[str, str]:
    return {"X-Development-User-Email": email, "X-Development-Role": role}


# --- get_development_current_user gate ---------------------------------------


def test_dev_headers_rejected_by_default_when_allow_dev_auth_disabled(client: TestClient) -> None:
    with _settings_override(APP_ENV="development", ALLOW_DEV_AUTH=False):
        response = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert response.status_code == 401


def test_dev_headers_accepted_only_with_explicit_allow_dev_auth_in_development(client: TestClient) -> None:
    with _settings_override(APP_ENV="development", ALLOW_DEV_AUTH=False):
        denied = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert denied.status_code == 401

    with _settings_override(APP_ENV="development", ALLOW_DEV_AUTH=True):
        allowed = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert allowed.status_code == 200


@pytest.mark.parametrize("app_env", ["test", "testing"])
def test_dev_headers_accepted_in_test_environments_with_flag_enabled(client: TestClient, app_env: str) -> None:
    with _settings_override(APP_ENV=app_env, ALLOW_DEV_AUTH=True):
        response = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert response.status_code == 200


def test_production_rejects_dev_headers_even_if_allow_dev_auth_is_enabled(client: TestClient) -> None:
    with _settings_override(APP_ENV="production", ALLOW_DEV_AUTH=True):
        response = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert response.status_code == 401


@pytest.mark.parametrize("app_env", ["staging", "pilot", "unknown"])
def test_other_non_dev_environments_reject_dev_headers_even_if_allow_dev_auth_is_enabled(
    client: TestClient, app_env: str
) -> None:
    with _settings_override(APP_ENV=app_env, ALLOW_DEV_AUTH=True):
        response = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert response.status_code == 401


def test_missing_app_env_cannot_result_in_dev_auth_access(client: TestClient) -> None:
    # An empty APP_ENV models a deployment where the variable was never set
    # and no meaningful default reached the running process - it must never
    # be treated as equivalent to "development".
    with _settings_override(APP_ENV="", ALLOW_DEV_AUTH=True):
        response = client.get("/api/v1/admin/organisations", headers=dev_headers())
    assert response.status_code == 401


# --- assert_dev_auth_policy_safe startup guard --------------------------------


def test_assert_dev_auth_policy_safe_refuses_production_with_allow_dev_auth_enabled() -> None:
    with _settings_override(APP_ENV="production", ALLOW_DEV_AUTH=True):
        with pytest.raises(RuntimeError, match="ALLOW_DEV_AUTH"):
            assert_dev_auth_policy_safe()


def test_assert_dev_auth_policy_safe_allows_production_with_allow_dev_auth_disabled() -> None:
    with _settings_override(APP_ENV="production", ALLOW_DEV_AUTH=False):
        assert_dev_auth_policy_safe()  # must not raise


def test_assert_dev_auth_policy_safe_allows_development_with_allow_dev_auth_enabled() -> None:
    with _settings_override(APP_ENV="development", ALLOW_DEV_AUTH=True):
        assert_dev_auth_policy_safe()  # must not raise


def test_create_app_refuses_unsafe_production_dev_auth_combination() -> None:
    with _settings_override(APP_ENV="production", ALLOW_DEV_AUTH=True):
        with pytest.raises(RuntimeError, match="ALLOW_DEV_AUTH"):
            create_app()


# --- normal session auth / RBAC are unaffected --------------------------------


def test_normal_session_auth_flow_is_unaffected_by_allow_dev_auth(client: TestClient) -> None:
    with _settings_override(ALLOW_DEV_AUTH=False):
        register = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Jane Doe",
                "email": "jane.doe@example.com",
                "password": "SuperSecure123",
                "confirm_password": "SuperSecure123",
                "organisation_name": "Example College",
            },
        )
        assert register.status_code == 201

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["data"]["user"]["email"] == "jane.doe@example.com"


def test_rbac_still_enforced_when_dev_auth_is_enabled(client: TestClient) -> None:
    with client.app.state.testing_session() as db:
        from app.db.models import Membership, Organisation, User, Workspace

        organisation = Organisation(name="Example College", slug="example-college")
        user = User(email="client-admin@example.test")
        workspace = Workspace(organisation=organisation, name="Admissions", slug="admissions")
        membership = Membership(organisation=organisation, user=user, role="client_admin")
        db.add_all([organisation, user, workspace, membership])
        db.commit()

    with _settings_override(APP_ENV="development", ALLOW_DEV_AUTH=True):
        response = client.get(
            "/api/v1/admin/organisations",
            headers=dev_headers("client-admin@example.test", "client_admin"),
        )
    assert response.status_code == 403

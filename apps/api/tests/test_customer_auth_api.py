from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.service import create_password_reset, hash_password, verify_password
from app.db.base import Base
from app.db.models import AuditEvent, AuthSession, Membership, Organisation, PasswordResetToken, User, Workspace
from app.db.session import get_db
from app.main import create_app


def build_client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_register_provisions_user_tenant_membership_workspace_and_audit() -> None:
    with build_client() as client:
        response = client.post("/api/v1/auth/register", json={
            "full_name": "Ari Patel",
            "email": "ari@example.com",
            "password": "SecurePass123",
            "confirm_password": "SecurePass123",
            "organisation_name": "Acme Support",
        })
        assert response.status_code == 201
        assert "yoranix_session" in response.cookies
        data = response.json()["data"]
        assert data["user"]["email"] == "ari@example.com"
        assert data["role"] == "org_owner"
        assert data["organisation"]["name"] == "Acme Support"
        assert data["workspace"]["name"] == "Default workspace"
        assert data["onboarding_complete"] is False

        with client.app.state.testing_session() as db:
            user = db.execute(select(User).where(User.email == "ari@example.com")).scalar_one()
            assert user.password_hash != "SecurePass123"
            assert verify_password("SecurePass123", user.password_hash)
            assert db.execute(select(Organisation)).scalar_one().slug == "acme-support"
            assert db.execute(select(Workspace)).scalar_one().slug == "default"
            assert db.execute(select(Membership)).scalar_one().role == "org_owner"
            assert db.execute(select(AuditEvent).where(AuditEvent.action == "auth.registration.provisioned")).scalar_one()


def test_duplicate_email_is_rejected_without_plain_password_exposure() -> None:
    with build_client() as client:
        payload = {"full_name": "Ari Patel", "email": "ari@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Acme"}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        duplicate = client.post("/api/v1/auth/register", json=payload)
        assert duplicate.status_code == 409
        assert "SecurePass123" not in duplicate.text
        with client.app.state.testing_session() as db:
            assert len(db.execute(select(User)).scalars().all()) == 1


def test_duplicate_organisation_slug_gets_unique_suffix() -> None:
    with build_client() as client:
        first = {"full_name": "One Owner", "email": "one@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Acme"}
        second = {**first, "email": "two@example.com"}
        assert client.post("/api/v1/auth/register", json=first).status_code == 201
        assert client.post("/api/v1/auth/register", json=second).status_code == 201
        with client.app.state.testing_session() as db:
            slugs = [org.slug for org in db.execute(select(Organisation).order_by(Organisation.slug)).scalars().all()]
            assert slugs == ["acme", "acme-2"]


def test_login_invalid_and_inactive_account_states() -> None:
    with build_client() as client:
        payload = {"full_name": "Ari Patel", "email": "ari@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Acme"}
        client.post("/api/v1/auth/register", json=payload)
        invalid = client.post("/api/v1/auth/login", json={"email": "ari@example.com", "password": "wrong", "remember": False})
        assert invalid.status_code == 401
        with client.app.state.testing_session() as db:
            user = db.execute(select(User).where(User.email == "ari@example.com")).scalar_one()
            user.status = "inactive"
            db.commit()
        inactive = client.post("/api/v1/auth/login", json={"email": "ari@example.com", "password": "SecurePass123", "remember": False})
        assert inactive.status_code == 403


def test_current_user_logout_and_session_revocation() -> None:
    with build_client() as client:
        client.post("/api/v1/auth/register", json={"full_name": "Ari Patel", "email": "ari@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Acme"})
        assert client.get("/api/v1/auth/me").status_code == 200
        logout = client.post("/api/v1/auth/logout")
        assert logout.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
        with client.app.state.testing_session() as db:
            assert db.execute(select(AuthSession)).scalar_one().revoked_at is not None


def test_session_tenant_isolation_blocks_cross_organisation_access() -> None:
    with build_client() as client:
        alpha = {"full_name": "Alpha Owner", "email": "alpha@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Alpha"}
        beta = {"full_name": "Beta Owner", "email": "beta@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Beta"}
        client.post("/api/v1/auth/register", json=alpha)
        with client.app.state.testing_session() as db:
            alpha_org = db.execute(select(Organisation).where(Organisation.slug == "alpha")).scalar_one()
            alpha_workspace = db.execute(select(Workspace).where(Workspace.organisation_id == alpha_org.id)).scalar_one()
        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/register", json=beta)
        denied = client.get(f"/api/v1/workspaces/{alpha_workspace.id}/settings", params={"organisation_id": alpha_org.id})
        assert denied.status_code == 403


def test_password_reset_token_updates_hash_and_cannot_be_reused() -> None:
    with build_client() as client:
        client.post("/api/v1/auth/register", json={"full_name": "Ari Patel", "email": "ari@example.com", "password": "SecurePass123", "confirm_password": "SecurePass123", "organisation_name": "Acme"})
        with client.app.state.testing_session() as db:
            token = create_password_reset(db, email="ari@example.com")
            assert token
            assert db.execute(select(PasswordResetToken)).scalar_one().token_hash != token
        reset = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewSecure123", "confirm_password": "NewSecure123"})
        assert reset.status_code == 200
        reused = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewSecure123", "confirm_password": "NewSecure123"})
        assert reused.status_code == 400
        login = client.post("/api/v1/auth/login", json={"email": "ari@example.com", "password": "NewSecure123", "remember": False})
        assert login.status_code == 200


def test_password_hash_helper_does_not_store_plaintext() -> None:
    hashed = hash_password("SecurePass123")
    assert hashed != "SecurePass123"
    assert verify_password("SecurePass123", hashed)
    assert not verify_password("wrong", hashed)

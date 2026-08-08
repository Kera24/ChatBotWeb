"""End-to-end tests for password-reset and email-verification delivery
(P0-2 of the launch readiness review) through the real /auth API routes,
using an in-memory TransactionalEmailProvider double so tests can inspect
exactly what would have been sent without any network call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.service import hash_token
from app.core.config import settings
from app.db.base import Base
from app.db.models import EmailVerificationToken, PasswordResetToken, User
from app.db.session import get_db
from app.email.contracts import EmailMessage, EmailSendResult
from app.email.providers.base import TransactionalEmailProvider
from app.main import create_app


def _register_payload() -> dict[str, str]:
    # A fresh, unique email per test avoids tripping the shared, module-level
    # auth_rate_limiter (12 attempts/60s per IP:email key, see
    # app.auth.rate_limit) across register()/forgot-password() calls made by
    # different tests in this file - not a workaround for anything these
    # tests are meant to exercise.
    unique = uuid4().hex[:10]
    return {
        "full_name": "Ari Patel",
        "email": f"ari-{unique}@example.com",
        "password": "SecurePass123",
        "confirm_password": "SecurePass123",
        "organisation_name": "Acme Support",
    }


class CapturingEmailProvider(TransactionalEmailProvider):
    provider_key = "capturing-test-double"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailSendResult:
        self.sent.append(message)
        return EmailSendResult(provider_key=self.provider_key, email_type=message.email_type, success=True, latency_ms=1, retry_count=0, provider_message_id="test-id")


class FailingEmailProvider(TransactionalEmailProvider):
    provider_key = "failing-test-double"

    def send(self, message: EmailMessage):  # noqa: ANN201
        from app.email.errors import EmailProviderUnavailableError

        raise EmailProviderUnavailableError("simulated provider outage")


def build_client(email_provider: TransactionalEmailProvider | None = None) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app = create_app()
    app.state.testing_session = TestingSession
    if email_provider is not None:
        app.state.email_provider = email_provider

    def override_get_db() -> Session:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


# --- password reset email ----------------------------------------------------


def test_forgot_password_sends_reset_email_with_working_url_for_known_account() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        provider.sent.clear()  # drop the verification email fired by registration

        response = client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        assert response.status_code == 200

        assert len(provider.sent) == 1
        message = provider.sent[0]
        assert message.email_type.value == "password_reset"
        assert message.to_email == payload["email"]
        assert f"{settings.WEB_ORIGIN}/reset-password?token=" in message.text_body

        # the token embedded in the email URL still works end-to-end
        token = message.text_body.split("token=")[1].split()[0].strip()
        reset = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewSecure123", "confirm_password": "NewSecure123"})
        assert reset.status_code == 200
        login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "NewSecure123", "remember": False})
        assert login.status_code == 200


def test_forgot_password_unknown_email_returns_identical_response_and_sends_nothing() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)

        known = client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        unknown = client.post("/api/v1/auth/forgot-password", json={"email": f"nobody-{uuid4().hex[:8]}@example.com"})

        assert known.status_code == unknown.status_code == 200
        assert known.json()["data"] == unknown.json()["data"]
        # exactly one email sent (for the known account) - nothing for "unknown"
        assert sum(1 for m in provider.sent if m.email_type.value == "password_reset") == 1


def test_forgot_password_no_token_leaks_into_the_api_response() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        response = client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        body_text = response.text
        # the only place the raw token should ever appear is inside the
        # "sent" email captured by the test double, never in the HTTP response
        sent_token = provider.sent[-1].text_body.split("token=")[1].split()[0].strip()
        assert sent_token not in body_text


def test_forgot_password_provider_failure_does_not_break_the_endpoint() -> None:
    payload = _register_payload()
    with build_client(FailingEmailProvider()) as client:
        client.post("/api/v1/auth/register", json=payload)
        response = client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        assert response.status_code == 200
        # the reset token was still created even though delivery failed
        with client.app.state.testing_session() as db:
            assert db.execute(select(PasswordResetToken)).scalar_one() is not None


def test_forgot_password_expired_reset_token_is_rejected() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        token = provider.sent[-1].text_body.split("token=")[1].split()[0].strip()
        with client.app.state.testing_session() as db:
            reset = db.execute(select(PasswordResetToken)).scalar_one()
            reset.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        response = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewSecure123", "confirm_password": "NewSecure123"})
        assert response.status_code == 400


def test_forgot_password_reused_reset_token_is_rejected() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        token = provider.sent[-1].text_body.split("token=")[1].split()[0].strip()
        first = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "NewSecure123", "confirm_password": "NewSecure123"})
        assert first.status_code == 200
        second = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "AnotherPass123", "confirm_password": "AnotherPass123"})
        assert second.status_code == 400


# --- email verification -------------------------------------------------------


def test_register_sends_verification_email_with_working_url() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        verification_emails = [m for m in provider.sent if m.email_type.value == "email_verification"]
        assert len(verification_emails) == 1
        message = verification_emails[0]
        assert message.to_email == payload["email"]
        assert f"{settings.WEB_ORIGIN}/verify-email?token=" in message.text_body

        token = message.text_body.split("token=")[1].split()[0].strip()
        verify = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verify.status_code == 200

        with client.app.state.testing_session() as db:
            user = db.execute(select(User).where(User.email == payload["email"])).scalar_one()
            assert user.email_verified_at is not None


def test_verify_email_expired_token_is_rejected() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        message = [m for m in provider.sent if m.email_type.value == "email_verification"][0]
        token = message.text_body.split("token=")[1].split()[0].strip()
        with client.app.state.testing_session() as db:
            verification = db.execute(select(EmailVerificationToken)).scalar_one()
            verification.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        response = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert response.status_code == 400


def test_verify_email_reused_token_is_rejected() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        message = [m for m in provider.sent if m.email_type.value == "email_verification"][0]
        token = message.text_body.split("token=")[1].split()[0].strip()
        first = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert first.status_code == 200
        second = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert second.status_code == 400


def test_verify_email_invalid_token_is_rejected() -> None:
    with build_client(CapturingEmailProvider()) as client:
        response = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token-not-a-real-token"})
        assert response.status_code == 400


def test_verify_email_does_not_reissue_a_token_once_already_verified() -> None:
    """create_email_verification returns None once the account is already
    verified - a second registration-adjacent trigger must not mint a fresh
    token for an already-verified user."""
    from app.auth.service import create_email_verification

    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        message = [m for m in provider.sent if m.email_type.value == "email_verification"][0]
        token = message.text_body.split("token=")[1].split()[0].strip()
        client.post("/api/v1/auth/verify-email", json={"token": token})

        with client.app.state.testing_session() as db:
            user = db.execute(select(User).where(User.email == payload["email"])).scalar_one()
            assert create_email_verification(db, user=user) is None


# --- token storage hygiene ----------------------------------------------------


def test_reset_token_is_never_stored_or_returned_in_plaintext() -> None:
    provider = CapturingEmailProvider()
    payload = _register_payload()
    with build_client(provider) as client:
        client.post("/api/v1/auth/register", json=payload)
        client.post("/api/v1/auth/forgot-password", json={"email": payload["email"]})
        token = provider.sent[-1].text_body.split("token=")[1].split()[0].strip()
        with client.app.state.testing_session() as db:
            stored = db.execute(select(PasswordResetToken)).scalar_one()
            assert stored.token_hash != token
            assert stored.token_hash == hash_token(token)

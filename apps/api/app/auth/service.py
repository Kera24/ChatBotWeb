from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AuditEvent, AuthSession, EmailVerificationToken, Membership, Organisation, PasswordResetToken, Subscription, User, Workspace

PASSWORD_ITERATIONS = 210_000
PASSWORD_SCHEME = "pbkdf2_sha256"
SESSION_TOKEN_BYTES = 32
RESET_TOKEN_BYTES = 32
VERIFICATION_TOKEN_BYTES = 32
SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class AuthError(Exception):
    pass


class DuplicateEmailError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InactiveAccountError(AuthError):
    pass


class InvalidResetTokenError(AuthError):
    pass


class InvalidVerificationTokenError(AuthError):
    pass


@dataclass(frozen=True)
class ProvisionedAccount:
    user: User
    organisation: Organisation
    workspace: Workspace
    membership: Membership


def normalise_email(email: str) -> str:
    return email.strip().lower()


def slugify(value: str) -> str:
    slug = SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    return slug[:80].strip("-") or "workspace"


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        scheme, iterations, salt, expected = stored_hash.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    secret = settings.AUTH_SESSION_HASH_SECRET.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def create_reset_token() -> str:
    return secrets.token_urlsafe(RESET_TOKEN_BYTES)


def create_verification_token() -> str:
    return secrets.token_urlsafe(VERIFICATION_TOKEN_BYTES)


def provision_account(db: Session, *, full_name: str, email: str, password: str, organisation_name: str) -> ProvisionedAccount:
    email = normalise_email(email)
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateEmailError()

    organisation_slug = unique_organisation_slug(db, slugify(organisation_name))
    workspace_slug = "default"
    user = User(email=email, full_name=full_name.strip(), password_hash=hash_password(password), status="active")
    organisation = Organisation(name=organisation_name.strip(), slug=organisation_slug, status="active", plan_key="starter")
    workspace = Workspace(organisation=organisation, name="Default workspace", slug=workspace_slug, status="active", default_language="en")
    membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
    subscription = Subscription(
        organisation=organisation,
        plan_key="starter",
        status="trialing",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=settings.BILLING_TRIAL_PERIOD_DAYS),
    )
    db.add_all([user, organisation, workspace, membership, subscription])
    db.flush()
    db.add(AuditEvent(
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        actor_user_id=user.id,
        action="auth.registration.provisioned",
        entity_type="user",
        entity_id=user.id,
        metadata_json={"organisation_slug": organisation.slug, "workspace_slug": workspace.slug, "role": membership.role},
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateEmailError()
    db.refresh(user)
    db.refresh(organisation)
    db.refresh(workspace)
    db.refresh(membership)
    return ProvisionedAccount(user=user, organisation=organisation, workspace=workspace, membership=membership)


def unique_organisation_slug(db: Session, base_slug: str) -> str:
    base = base_slug[:72] or "organisation"
    candidate = base
    suffix = 1
    while db.execute(select(Organisation.id).where(Organisation.slug == candidate)).scalar_one_or_none() is not None:
        suffix += 1
        candidate = f"{base}-{suffix}"[:120]
    return candidate


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == normalise_email(email))).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    if user.status != "active":
        raise InactiveAccountError()
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def create_auth_session(db: Session, *, user: User, user_agent: str | None, ip_address: str | None, remember: bool = False) -> tuple[str, AuthSession]:
    token = create_session_token()
    ttl_days = settings.AUTH_REMEMBER_SESSION_DAYS if remember else settings.AUTH_SESSION_DAYS
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=(user_agent or "")[:512] or None,
        ip_address=(ip_address or "")[:80] or None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def get_user_for_session_token(db: Session, token: str | None) -> tuple[User, AuthSession] | None:
    if not token:
        return None
    token_hash = hash_token(token)
    statement = select(AuthSession, User).join(User, User.id == AuthSession.user_id).where(AuthSession.token_hash == token_hash)
    row = db.execute(statement).one_or_none()
    if row is None:
        return None
    session, user = row
    now = datetime.now(timezone.utc)
    expires_at = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    if session.revoked_at is not None or expires_at <= now or user.status != "active":
        return None
    return user, session


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token))).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()


def create_password_reset(db: Session, *, email: str) -> str | None:
    user = db.execute(select(User).where(User.email == normalise_email(email))).scalar_one_or_none()
    if user is None or user.status != "active" or not user.password_hash:
        return None
    token = create_reset_token()
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token), expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.AUTH_PASSWORD_RESET_MINUTES)))
    db.commit()
    return token


def reset_password(db: Session, *, token: str, password: str) -> User:
    reset = db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if reset is None or reset.used_at is not None:
        raise InvalidResetTokenError()
    expires_at = reset.expires_at if reset.expires_at.tzinfo else reset.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise InvalidResetTokenError()
    user = db.get(User, reset.user_id)
    if user is None or user.status != "active":
        raise InvalidResetTokenError()
    user.password_hash = hash_password(password)
    reset.used_at = now
    db.add(AuditEvent(
        organisation_id=_first_membership(db, user.id).organisation_id,
        workspace_id=_first_workspace(db, _first_membership(db, user.id).organisation_id).id,
        actor_user_id=user.id,
        action="auth.password.reset",
        entity_type="user",
        entity_id=user.id,
        metadata_json={},
    ))
    db.commit()
    db.refresh(user)
    return user


def create_email_verification(db: Session, *, user: User) -> str | None:
    if user.email_verified_at is not None:
        return None
    token = create_verification_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.AUTH_EMAIL_VERIFICATION_MINUTES),
        )
    )
    db.commit()
    return token


def verify_email(db: Session, *, token: str) -> User:
    verification = db.execute(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(token))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if verification is None or verification.used_at is not None:
        raise InvalidVerificationTokenError()
    expires_at = verification.expires_at if verification.expires_at.tzinfo else verification.expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise InvalidVerificationTokenError()
    user = db.get(User, verification.user_id)
    if user is None or user.status != "active":
        raise InvalidVerificationTokenError()
    user.email_verified_at = now
    verification.used_at = now
    db.add(AuditEvent(
        organisation_id=_first_membership(db, user.id).organisation_id,
        workspace_id=_first_workspace(db, _first_membership(db, user.id).organisation_id).id,
        actor_user_id=user.id,
        action="auth.email.verified",
        entity_type="user",
        entity_id=user.id,
        metadata_json={},
    ))
    db.commit()
    db.refresh(user)
    return user


def _first_membership(db: Session, user_id: str) -> Membership:
    membership = db.execute(select(Membership).where(Membership.user_id == user_id, Membership.status == "active").order_by(Membership.created_at)).scalar_one()
    return membership


def _first_workspace(db: Session, organisation_id: str) -> Workspace:
    return db.execute(select(Workspace).where(Workspace.organisation_id == organisation_id, Workspace.status == "active").order_by(Workspace.created_at)).scalar_one()


def session_context(db: Session, user: User) -> dict[str, object] | None:
    membership = db.execute(select(Membership).where(Membership.user_id == user.id, Membership.status == "active").order_by(Membership.created_at)).scalar_one_or_none()
    if membership is None:
        return None
    organisation = db.get(Organisation, membership.organisation_id)
    workspace = db.execute(select(Workspace).where(Workspace.organisation_id == membership.organisation_id, Workspace.status == "active", Workspace.deleted_at.is_(None)).order_by(Workspace.created_at)).scalar_one_or_none()
    if organisation is None or organisation.status != "active" or workspace is None:
        return None
    return {
        "user": user,
        "membership": membership,
        "organisation": organisation,
        "workspace": workspace,
        "onboarding_complete": user.onboarding_completed_at is not None,
    }


def complete_onboarding(db: Session, user: User) -> None:
    if user.onboarding_completed_at is None:
        user.onboarding_completed_at = datetime.now(timezone.utc)
        db.commit()

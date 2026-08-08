from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.deps import AuthenticatedUserDependency, DbSession
from app.auth.rate_limit import auth_rate_limiter
from app.auth.service import (
    DuplicateEmailError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    InvalidVerificationTokenError,
    authenticate_user,
    complete_onboarding,
    create_auth_session,
    create_email_verification,
    create_password_reset,
    provision_account,
    reset_password,
    revoke_session,
    session_context,
    verify_email,
)
from app.core.config import settings
from app.email.dependencies import get_email_provider
from app.email.providers.base import TransactionalEmailProvider
from app.email.service import send_password_reset_email, send_verification_email
from app.schemas.auth import AuthContextRead, AuthMessageRead, ForgotPasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest, VerifyEmailRequest
from app.schemas.common import success_response

router = APIRouter()

EmailProviderDependency = Annotated[TransactionalEmailProvider, Depends(get_email_provider)]


def _client_key(request: Request, email: str | None = None) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    return f"{ip}:{(email or '').lower()}"


def _set_session_cookie(response: Response, token: str, *, remember: bool = False) -> None:
    response.set_cookie(
        settings.AUTH_SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        samesite="lax",
        max_age=(settings.AUTH_REMEMBER_SESSION_DAYS if remember else settings.AUTH_SESSION_DAYS) * 86400,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.AUTH_SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax")


def _auth_context(db: DbSession, user) -> AuthContextRead:
    context = session_context(db, user)
    if context is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access is not active.")
    organisation = context["organisation"]
    workspace = context["workspace"]
    membership = context["membership"]
    onboarding_complete = bool(context["onboarding_complete"])
    return AuthContextRead(
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "email_verified": user.email_verified_at is not None,
            "onboarding_complete": onboarding_complete,
        },
        organisation={"name": organisation.name, "slug": organisation.slug, "plan_key": organisation.plan_key, "status": organisation.status},
        workspace={"name": workspace.name, "slug": workspace.slug, "status": workspace.status},
        membership={"role": membership.role, "status": membership.status},
        organisation_id=organisation.id,
        workspace_id=workspace.id,
        role=membership.role,
        onboarding_complete=onboarding_complete,
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response, db: DbSession, email_provider: EmailProviderDependency) -> dict[str, object]:
    if not auth_rate_limiter.check(_client_key(request, payload.email)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many authentication attempts. Try again shortly.")
    try:
        account = provision_account(db, full_name=payload.full_name, email=payload.email, password=payload.password, organisation_name=payload.organisation_name)
    except DuplicateEmailError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from exc
    token, _session = create_auth_session(db, user=account.user, user_agent=request.headers.get("user-agent"), ip_address=_client_key(request), remember=False)
    _set_session_cookie(response, token)
    # Best-effort: a verification-email delivery failure must never block
    # registration - create_email_verification/send_verification_email are
    # already fail-safe internally (see app.email.service._send).
    verification_token = create_email_verification(db, user=account.user)
    if verification_token is not None:
        send_verification_email(email_provider, to_email=account.user.email, verification_token=verification_token)
    return success_response(_auth_context(db, account.user).model_dump(mode="json"))


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db: DbSession) -> dict[str, object]:
    if not auth_rate_limiter.check(_client_key(request, payload.email)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many authentication attempts. Try again shortly.")
    try:
        user = authenticate_user(db, email=payload.email, password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.") from exc
    except InactiveAccountError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is inactive.") from exc
    token, _session = create_auth_session(db, user=user, user_agent=request.headers.get("user-agent"), ip_address=_client_key(request), remember=payload.remember)
    _set_session_cookie(response, token, remember=payload.remember)
    return success_response(_auth_context(db, user).model_dump(mode="json"))


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession) -> dict[str, object]:
    revoke_session(db, request.cookies.get(settings.AUTH_SESSION_COOKIE_NAME))
    _clear_session_cookie(response)
    return success_response(AuthMessageRead(message="Signed out.").model_dump(mode="json"))


@router.get("/me")
def current_user(current_user: AuthenticatedUserDependency, db: DbSession) -> dict[str, object]:
    return success_response(_auth_context(db, current_user).model_dump(mode="json"))


@router.post("/onboarding/complete")
def complete_onboarding_endpoint(current_user: AuthenticatedUserDependency, db: DbSession) -> dict[str, object]:
    complete_onboarding(db, current_user)
    db.refresh(current_user)
    return success_response(_auth_context(db, current_user).model_dump(mode="json"))


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: DbSession, email_provider: EmailProviderDependency) -> dict[str, object]:
    if not auth_rate_limiter.check(_client_key(request, payload.email)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many authentication attempts. Try again shortly.")
    # create_password_reset returns None for both "no such account" and "account
    # exists but has no password" - the response below is identical either way,
    # so this never reveals account existence. reset_delivery_supported/the
    # message text reflect only which provider is configured deployment-wide
    # (never whether a matching account was found).
    reset_token = create_password_reset(db, email=payload.email)
    if reset_token is not None:
        send_password_reset_email(email_provider, to_email=payload.email, reset_token=reset_token)
    delivery_supported = email_provider.provider_key != "dev"
    message = (
        "If an account exists, password reset instructions have been sent."
        if delivery_supported
        else "If an account exists, password reset instructions will be sent when email delivery is configured."
    )
    return success_response(AuthMessageRead(message=message, reset_delivery_supported=delivery_supported).model_dump(mode="json"))


@router.post("/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, db: DbSession) -> dict[str, object]:
    try:
        reset_password(db, token=payload.token, password=payload.password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset link is invalid or expired.") from exc
    return success_response(AuthMessageRead(message="Password updated. You can now log in.").model_dump(mode="json"))


@router.post("/verify-email")
def verify_email_endpoint(payload: VerifyEmailRequest, db: DbSession) -> dict[str, object]:
    try:
        verify_email(db, token=payload.token)
    except InvalidVerificationTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email verification link is invalid or expired.") from exc
    return success_response(AuthMessageRead(message="Email verified. You can now log in.").model_dump(mode="json"))

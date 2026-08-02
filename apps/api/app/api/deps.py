from dataclasses import dataclass
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.service import get_user_for_session_token
from app.core.config import settings
from app.db.session import get_db
from app.repositories.membership_repository import get_membership_for_organisation
from app.repositories.user_repository import get_active_user_by_email

DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class DevelopmentCurrentUser:
    email: str
    role: str
    user_id: str | None = None


AuthenticatedUserDependency = Annotated[object, Depends(lambda: None)]


def get_authenticated_user(
    request: Request,
    db: DbSession,
    yoranix_session: Annotated[str | None, Cookie(alias="yoranix_session")] = None,
):
    token = yoranix_session or request.cookies.get(settings.AUTH_SESSION_COOKIE_NAME)
    resolved = get_user_for_session_token(db, token)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    user, _session = resolved
    return user


AuthenticatedUserDependency = Annotated[object, Depends(get_authenticated_user)]


def get_development_current_user(
    db: DbSession,
    request: Request,
    x_development_user_email: Annotated[
        str | None,
        Header(description="Development-only user email placeholder."),
    ] = None,
    x_development_role: Annotated[str | None, Header()] = None,
) -> DevelopmentCurrentUser:
    resolved = get_user_for_session_token(db, request.cookies.get(settings.AUTH_SESSION_COOKIE_NAME))
    if resolved is not None:
        user, _session = resolved
        membership = None
        if user.id:
            from sqlalchemy import select
            from app.db.models import Membership
            membership = db.execute(select(Membership).where(Membership.user_id == user.id, Membership.status == "active").order_by(Membership.created_at)).scalar_one_or_none()
        return DevelopmentCurrentUser(email=user.email, role=membership.role if membership is not None else "viewer", user_id=user.id)

    if settings.APP_ENV.lower() not in {"development", "test", "testing"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    email = x_development_user_email or "dev-super-admin@example.test"
    role = x_development_role or "super_admin"
    user = get_active_user_by_email(db, email=email)
    if role != "super_admin" and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development user does not exist.",
        )

    return DevelopmentCurrentUser(
        email=email,
        role=role,
        user_id=user.id if user is not None else None,
    )


CurrentUserDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(get_development_current_user),
]


def require_super_admin(current_user: CurrentUserDependency) -> DevelopmentCurrentUser:
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="super_admin role required.",
        )
    return current_user


SuperAdminDependency = Annotated[
    DevelopmentCurrentUser,
    Depends(require_super_admin),
]


def require_organisation_role(
    allowed_roles: set[str],
) -> Callable[[str, DbSession, CurrentUserDependency], DevelopmentCurrentUser]:
    def dependency(
        organisation_id: str,
        db: DbSession,
        current_user: CurrentUserDependency,
    ) -> DevelopmentCurrentUser:
        if current_user.role == "super_admin":
            return current_user

        if current_user.user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user required.",
            )

        membership = get_membership_for_organisation(
            db,
            organisation_id=organisation_id,
            user_id=current_user.user_id,
        )
        if membership is None or membership.status != "active" or membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organisation membership with an allowed role is required.",
            )

        return DevelopmentCurrentUser(email=current_user.email, role=membership.role, user_id=current_user.user_id)

    return dependency

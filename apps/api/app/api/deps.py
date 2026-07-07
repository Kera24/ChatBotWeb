from dataclasses import dataclass
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.membership_repository import get_membership_for_organisation
from app.repositories.user_repository import get_active_user_by_email

DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class DevelopmentCurrentUser:
    email: str
    role: str
    user_id: str | None = None


def get_development_current_user(
    db: DbSession,
    x_development_user_email: Annotated[
        str,
        Header(description="Development-only user email placeholder."),
    ] = "dev-super-admin@example.test",
    x_development_role: Annotated[str, Header()] = "super_admin",
) -> DevelopmentCurrentUser:
    """Development-only current-user placeholder until real auth exists.

    This is not production authentication. It only gives the API an explicit
    current-user shape so RBAC and tenant membership checks can be developed
    and tested before hosted auth is integrated.
    """

    user = get_active_user_by_email(db, email=x_development_user_email)
    if x_development_role != "super_admin" and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development user does not exist.",
        )

    return DevelopmentCurrentUser(
        email=x_development_user_email,
        role=x_development_role,
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
                detail="Authenticated development user required.",
            )

        membership = get_membership_for_organisation(
            db,
            organisation_id=organisation_id,
            user_id=current_user.user_id,
        )
        if membership is None or membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organisation membership with an allowed role is required.",
            )

        return current_user

    return dependency

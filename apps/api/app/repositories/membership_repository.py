from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Membership, User

VALID_ORGANISATION_ROLES = {"org_owner", "client_admin", "contributor", "viewer"}
VALID_MEMBERSHIP_STATUSES = {"active", "inactive"}


def get_membership_for_organisation(
    db: Session,
    *,
    organisation_id: str,
    user_id: str,
) -> Membership | None:
    statement = select(Membership).where(
        Membership.organisation_id == organisation_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    )
    return db.execute(statement).scalar_one_or_none()


def get_membership_by_id(
    db: Session,
    *,
    organisation_id: str,
    membership_id: str,
) -> Membership | None:
    statement = (
        select(Membership)
        .options(joinedload(Membership.user), joinedload(Membership.organisation))
        .where(Membership.organisation_id == organisation_id, Membership.id == membership_id)
    )
    return db.execute(statement).scalar_one_or_none()


def list_memberships_for_organisation(
    db: Session,
    *,
    organisation_id: str,
) -> list[Membership]:
    statement = (
        select(Membership)
        .join(Membership.user)
        .options(joinedload(Membership.user), joinedload(Membership.organisation))
        .where(Membership.organisation_id == organisation_id)
        .order_by(User.email.asc())
    )
    return list(db.execute(statement).scalars().all())

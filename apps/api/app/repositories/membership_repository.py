from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Membership


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

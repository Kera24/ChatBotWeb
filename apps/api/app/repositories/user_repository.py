from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


def get_active_user_by_email(
    db: Session,
    *,
    email: str,
) -> User | None:
    statement = select(User).where(
        User.email == email,
        User.status == "active",
    )
    return db.execute(statement).scalar_one_or_none()

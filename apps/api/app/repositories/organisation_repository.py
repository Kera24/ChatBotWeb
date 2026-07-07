from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Organisation


def create_organisation(
    db: Session,
    *,
    name: str,
    slug: str,
) -> Organisation:
    organisation = Organisation(name=name, slug=slug)
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


def get_active_organisation(
    db: Session,
    *,
    organisation_id: str,
) -> Organisation | None:
    statement = select(Organisation).where(
        Organisation.id == organisation_id,
        Organisation.status == "active",
        Organisation.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def list_active_organisations(db: Session) -> list[Organisation]:
    statement = (
        select(Organisation)
        .where(
            Organisation.status == "active",
            Organisation.deleted_at.is_(None),
        )
        .order_by(Organisation.name)
    )
    return list(db.execute(statement).scalars().all())

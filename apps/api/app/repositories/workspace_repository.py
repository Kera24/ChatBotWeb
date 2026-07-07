from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Workspace


def create_workspace_for_organisation(
    db: Session,
    *,
    organisation_id: str,
    name: str,
    slug: str,
    default_language: str = "en",
) -> Workspace:
    workspace = Workspace(
        organisation_id=organisation_id,
        name=name,
        slug=slug,
        default_language=default_language,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_workspace_for_organisation(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
) -> Workspace | None:
    statement = select(Workspace).where(
        Workspace.id == workspace_id,
        Workspace.organisation_id == organisation_id,
        Workspace.status == "active",
        Workspace.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def list_workspaces_for_organisation(
    db: Session,
    *,
    organisation_id: str,
) -> list[Workspace]:
    statement = (
        select(Workspace)
        .where(
            Workspace.organisation_id == organisation_id,
            Workspace.status == "active",
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.name)
    )
    return list(db.execute(statement).scalars().all())

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WidgetConfiguration


def get_configuration_for_credential(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> WidgetConfiguration | None:
    statement = select(WidgetConfiguration).where(
        WidgetConfiguration.organisation_id == organisation_id,
        WidgetConfiguration.workspace_id == workspace_id,
        WidgetConfiguration.credential_id == credential_id,
    )
    return db.execute(statement).scalar_one_or_none()


def create_configuration_record(db: Session, configuration: WidgetConfiguration) -> WidgetConfiguration:
    db.add(configuration)
    db.flush()
    return configuration

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Widget, WidgetConfiguration, WidgetConfigurationRevision


def get_configuration_for_credential(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> WidgetConfiguration | WidgetConfigurationRevision | None:
    widget = db.execute(
        select(Widget).where(
            Widget.organisation_id == organisation_id,
            Widget.workspace_id == workspace_id,
            Widget.public_credential_id == credential_id,
            Widget.archived_at.is_(None),
        )
    ).scalar_one_or_none()
    if widget is not None and widget.active_published_revision_id:
        revision = db.execute(
            select(WidgetConfigurationRevision).where(
                WidgetConfigurationRevision.id == widget.active_published_revision_id,
                WidgetConfigurationRevision.widget_id == widget.id,
                WidgetConfigurationRevision.organisation_id == organisation_id,
                WidgetConfigurationRevision.workspace_id == workspace_id,
                WidgetConfigurationRevision.status == "published",
            )
        ).scalar_one_or_none()
        if revision is not None:
            return revision

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
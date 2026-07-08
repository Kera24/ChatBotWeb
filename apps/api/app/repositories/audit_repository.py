from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def add_audit_event(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_user_id: str | None = None,
    document_id: str | None = None,
    document_version_id: str | None = None,
    previous_status: str | None = None,
    new_status: str | None = None,
    metadata_json: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        document_id=document_id,
        document_version_id=document_version_id,
        previous_status=previous_status,
        new_status=new_status,
        metadata_json=metadata_json,
    )
    db.add(event)
    return event


def list_audit_events_for_workspace(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    limit: int = 100,
) -> list[AuditEvent]:
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.organisation_id == organisation_id,
            AuditEvent.workspace_id == workspace_id,
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def list_audit_events_for_organisation(
    db: Session,
    *,
    organisation_id: str,
    limit: int = 100,
) -> list[AuditEvent]:
    statement = (
        select(AuditEvent)
        .where(AuditEvent.organisation_id == organisation_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())

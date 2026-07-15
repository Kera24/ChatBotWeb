from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import PublicMessageRequest


def create_received(db: Session, record: PublicMessageRequest) -> PublicMessageRequest:
    db.add(record)
    db.flush()
    return record


def get_by_session_and_key_hash(db: Session, *, public_session_id: str, idempotency_key_hash: str) -> PublicMessageRequest | None:
    statement = select(PublicMessageRequest).where(
        PublicMessageRequest.public_session_id == public_session_id,
        PublicMessageRequest.idempotency_key_hash == idempotency_key_hash,
        PublicMessageRequest.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def get_by_tenant_record_id(db: Session, *, organisation_id: str, workspace_id: str, record_id: str) -> PublicMessageRequest | None:
    statement = select(PublicMessageRequest).where(
        PublicMessageRequest.id == record_id,
        PublicMessageRequest.organisation_id == organisation_id,
        PublicMessageRequest.workspace_id == workspace_id,
        PublicMessageRequest.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def transition_received_to_processing(db: Session, *, organisation_id: str, workspace_id: str, record_id: str, now: datetime) -> PublicMessageRequest | None:
    result = db.execute(
        update(PublicMessageRequest)
        .where(
            PublicMessageRequest.id == record_id,
            PublicMessageRequest.organisation_id == organisation_id,
            PublicMessageRequest.workspace_id == workspace_id,
            PublicMessageRequest.status == "received",
            PublicMessageRequest.deleted_at.is_(None),
        )
        .values(status="processing", processing_started_at=now, updated_at=now)
    )
    db.flush()
    if result.rowcount != 1:
        return None
    return get_by_tenant_record_id(db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id)


def transition_processing_to_completed(db: Session, *, organisation_id: str, workspace_id: str, record_id: str, response_snapshot: dict, user_message_id: str | None, assistant_message_id: str | None, now: datetime) -> PublicMessageRequest | None:
    result = db.execute(
        update(PublicMessageRequest)
        .where(
            PublicMessageRequest.id == record_id,
            PublicMessageRequest.organisation_id == organisation_id,
            PublicMessageRequest.workspace_id == workspace_id,
            PublicMessageRequest.status == "processing",
            PublicMessageRequest.deleted_at.is_(None),
        )
        .values(
            status="completed",
            response_snapshot_json=response_snapshot,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            completed_at=now,
            updated_at=now,
        )
    )
    db.flush()
    if result.rowcount != 1:
        return None
    return get_by_tenant_record_id(db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id)


def transition_processing_to_failed(db: Session, *, organisation_id: str, workspace_id: str, record_id: str, error_code: str, now: datetime) -> PublicMessageRequest | None:
    result = db.execute(
        update(PublicMessageRequest)
        .where(
            PublicMessageRequest.id == record_id,
            PublicMessageRequest.organisation_id == organisation_id,
            PublicMessageRequest.workspace_id == workspace_id,
            PublicMessageRequest.status == "processing",
            PublicMessageRequest.deleted_at.is_(None),
        )
        .values(status="failed", error_code=error_code, failed_at=now, updated_at=now)
    )
    db.flush()
    if result.rowcount != 1:
        return None
    return get_by_tenant_record_id(db, organisation_id=organisation_id, workspace_id=workspace_id, record_id=record_id)


def list_expired_for_cleanup(db: Session, *, now: datetime, limit: int = 500) -> list[PublicMessageRequest]:
    statement = select(PublicMessageRequest).where(PublicMessageRequest.expires_at <= now).limit(limit)
    return list(db.execute(statement).scalars().all())

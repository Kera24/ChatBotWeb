from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access.sessions.contracts import PUBLIC_SESSION_TERMINAL_STATUSES
from app.db.models import ChatSession, PublicSession


class PublicSessionTokenCollisionError(RuntimeError):
    pass


def create_session(db: Session, session: PublicSession) -> PublicSession:
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise PublicSessionTokenCollisionError("Public session token ID collided.") from exc
    return session


def get_by_token_id_for_verification(db: Session, *, public_token_id: str) -> PublicSession | None:
    statement = select(PublicSession).where(PublicSession.public_token_id == public_token_id, PublicSession.deleted_at.is_(None))
    return db.execute(statement).scalar_one_or_none()


def get_by_tenant_session_id(db: Session, *, organisation_id: str, workspace_id: str, session_id: str) -> PublicSession | None:
    statement = select(PublicSession).where(
        PublicSession.id == session_id,
        PublicSession.organisation_id == organisation_id,
        PublicSession.workspace_id == workspace_id,
        PublicSession.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def update_valid_activity(db: Session, session: PublicSession, *, now: datetime, expires_at: datetime) -> PublicSession:
    if session.status in PUBLIC_SESSION_TERMINAL_STATUSES:
        return session
    session.last_activity_at = now
    session.expires_at = expires_at
    db.add(session)
    db.flush()
    return session


def atomically_increment_message_count(db: Session, *, organisation_id: str, workspace_id: str, session_id: str, max_messages: int, now: datetime, expires_at: datetime) -> PublicSession | None:
    statement = (
        update(PublicSession)
        .where(
            PublicSession.id == session_id,
            PublicSession.organisation_id == organisation_id,
            PublicSession.workspace_id == workspace_id,
            PublicSession.status == "active",
            PublicSession.deleted_at.is_(None),
            PublicSession.message_count < max_messages,
        )
        .values(
            message_count=PublicSession.message_count + 1,
            last_activity_at=now,
            expires_at=expires_at,
            updated_at=now,
        )
    )
    result = db.execute(statement)
    if result.rowcount != 1:
        db.flush()
        return None
    db.flush()
    return get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)


def attach_conversation_once(db: Session, *, organisation_id: str, workspace_id: str, session_id: str, conversation_id: str, now: datetime) -> PublicSession:
    session = get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)
    if session is None:
        raise ValueError("Public session was not found in tenant scope.")
    if session.conversation_id is not None:
        return session
    conversation = db.execute(
        select(ChatSession).where(
            ChatSession.id == conversation_id,
            ChatSession.organisation_id == organisation_id,
            ChatSession.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise ValueError("Conversation does not belong to the public session tenant.")
    if session.conversation_id is None:
        result = db.execute(
            update(PublicSession)
            .where(
                PublicSession.id == session_id,
                PublicSession.organisation_id == organisation_id,
                PublicSession.workspace_id == workspace_id,
                PublicSession.conversation_id.is_(None),
                PublicSession.status == "active",
                PublicSession.deleted_at.is_(None),
            )
            .values(conversation_id=conversation_id, updated_at=now)
        )
        db.flush()
        if result.rowcount == 1:
            refreshed = get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)
            if refreshed is not None:
                return refreshed
    refreshed = get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)
    if refreshed is None:
        raise ValueError("Public session was not found in tenant scope.")
    return refreshed


def mark_status(db: Session, *, organisation_id: str, workspace_id: str, session_id: str, status: str, now: datetime) -> PublicSession | None:
    values: dict[str, object] = {"status": status, "updated_at": now}
    if status == "completed":
        values["completed_at"] = now
    elif status == "expired":
        values["blocked_at"] = None
    elif status == "revoked":
        values["revoked_at"] = now
    elif status == "blocked":
        values["blocked_at"] = now
    result = db.execute(
        update(PublicSession)
        .where(
            PublicSession.id == session_id,
            PublicSession.organisation_id == organisation_id,
            PublicSession.workspace_id == workspace_id,
            PublicSession.status == "active",
            PublicSession.deleted_at.is_(None),
        )
        .values(**values)
    )
    db.flush()
    if result.rowcount != 1:
        return get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)
    return get_by_tenant_session_id(db, organisation_id=organisation_id, workspace_id=workspace_id, session_id=session_id)


def list_active_sessions_for_credential(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> list[PublicSession]:
    statement = select(PublicSession).where(
        PublicSession.organisation_id == organisation_id,
        PublicSession.workspace_id == workspace_id,
        PublicSession.credential_id == credential_id,
        PublicSession.status == "active",
        PublicSession.deleted_at.is_(None),
    )
    return list(db.execute(statement).scalars().all())


def mark_expired_before(db: Session, *, now: datetime, limit: int = 500) -> int:
    sessions = list(
        db.execute(
            select(PublicSession.id)
            .where(
                PublicSession.status == "active",
                PublicSession.deleted_at.is_(None),
                or_expired(now),
            )
            .limit(limit)
        ).scalars().all()
    )
    if not sessions:
        return 0
    result = db.execute(update(PublicSession).where(PublicSession.id.in_(sessions)).values(status="expired", updated_at=now))
    db.flush()
    return int(result.rowcount or 0)


def or_expired(now: datetime):
    return and_((PublicSession.expires_at <= now) | (PublicSession.absolute_expires_at <= now))


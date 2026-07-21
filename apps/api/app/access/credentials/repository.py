from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CredentialAllowedOrigin, PublicCredential


def create_credential_record(db: Session, credential: PublicCredential) -> PublicCredential:
    db.add(credential)
    db.flush()
    return credential


def list_workspace_credentials(db: Session, *, organisation_id: str, workspace_id: str) -> list[PublicCredential]:
    statement = (
        select(PublicCredential)
        .where(
            PublicCredential.organisation_id == organisation_id,
            PublicCredential.workspace_id == workspace_id,
            PublicCredential.deleted_at.is_(None),
        )
        .order_by(PublicCredential.created_at.desc(), PublicCredential.id.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_credential_for_workspace(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str) -> PublicCredential | None:
    statement = select(PublicCredential).where(
        PublicCredential.id == credential_id,
        PublicCredential.organisation_id == organisation_id,
        PublicCredential.workspace_id == workspace_id,
        PublicCredential.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def resolve_credential_by_public_identifier(db: Session, *, public_identifier: str) -> PublicCredential | None:
    statement = select(PublicCredential).where(
        PublicCredential.public_identifier == public_identifier,
        PublicCredential.deleted_at.is_(None),
    )
    return db.execute(statement).scalar_one_or_none()


def update_credential_status(db: Session, credential: PublicCredential, *, status: str) -> PublicCredential:
    credential.status = status
    db.add(credential)
    db.flush()
    return credential


def list_rotation_group(db: Session, *, organisation_id: str, workspace_id: str, rotation_group_id: str) -> list[PublicCredential]:
    statement = (
        select(PublicCredential)
        .where(
            PublicCredential.organisation_id == organisation_id,
            PublicCredential.workspace_id == workspace_id,
            PublicCredential.rotation_group_id == rotation_group_id,
            PublicCredential.deleted_at.is_(None),
        )
        .order_by(PublicCredential.created_at, PublicCredential.id)
    )
    return list(db.execute(statement).scalars().all())


def list_credential_origins(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, active_only: bool = True) -> list[CredentialAllowedOrigin]:
    statement = select(CredentialAllowedOrigin).where(
        CredentialAllowedOrigin.organisation_id == organisation_id,
        CredentialAllowedOrigin.workspace_id == workspace_id,
        CredentialAllowedOrigin.credential_id == credential_id,
    )
    if active_only:
        statement = statement.where(CredentialAllowedOrigin.active.is_(True))
    statement = statement.order_by(CredentialAllowedOrigin.hostname, CredentialAllowedOrigin.scheme, CredentialAllowedOrigin.port)
    return list(db.execute(statement).scalars().all())


def get_origin_for_credential(db: Session, *, organisation_id: str, workspace_id: str, credential_id: str, origin_id: str) -> CredentialAllowedOrigin | None:
    statement = select(CredentialAllowedOrigin).where(
        CredentialAllowedOrigin.id == origin_id,
        CredentialAllowedOrigin.organisation_id == organisation_id,
        CredentialAllowedOrigin.workspace_id == workspace_id,
        CredentialAllowedOrigin.credential_id == credential_id,
    )
    return db.execute(statement).scalar_one_or_none()

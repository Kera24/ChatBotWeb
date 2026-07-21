from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.origin_validation.contracts import AllowedOriginRecord
from app.db.models import CredentialAllowedOrigin


def list_active_origins_for_credential(db: Session, *, credential_id: str, environment: str) -> list[AllowedOriginRecord]:
    statement = (
        select(CredentialAllowedOrigin)
        .where(
            CredentialAllowedOrigin.credential_id == credential_id,
            CredentialAllowedOrigin.environment == environment,
            CredentialAllowedOrigin.active.is_(True),
        )
        .order_by(CredentialAllowedOrigin.hostname, CredentialAllowedOrigin.scheme, CredentialAllowedOrigin.port)
    )
    return [_to_record(row) for row in db.execute(statement).scalars().all()]


def get_origin_for_credential_scope(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    credential_id: str,
    origin_id: str,
) -> AllowedOriginRecord | None:
    statement = select(CredentialAllowedOrigin).where(
        CredentialAllowedOrigin.id == origin_id,
        CredentialAllowedOrigin.organisation_id == organisation_id,
        CredentialAllowedOrigin.workspace_id == workspace_id,
        CredentialAllowedOrigin.credential_id == credential_id,
    )
    row = db.execute(statement).scalar_one_or_none()
    return _to_record(row) if row else None


def _to_record(row: CredentialAllowedOrigin) -> AllowedOriginRecord:
    return AllowedOriginRecord(
        origin_id=row.id,
        credential_id=row.credential_id,
        scheme=row.scheme,
        hostname=row.hostname,
        port=row.port,
        wildcard_subdomains=row.wildcard_subdomains,
        environment=row.environment,
        active=row.active,
    )

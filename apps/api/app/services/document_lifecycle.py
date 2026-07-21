from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Document, DocumentVersion
from app.repositories.audit_repository import add_audit_event
from app.repositories.document_repository import (
    get_document_for_workspace,
    get_document_version_for_workspace,
)


class InvalidLifecycleTransition(ValueError):
    pass


class LifecycleTargetNotFound(LookupError):
    pass


DOCUMENT_TRANSITIONS: dict[str, set[str]] = {
    "uploaded": {"processing"},
    "processing": {"ready", "failed"},
    "ready": {"archived", "expired"},
    "failed": set(),
    "archived": set(),
    "expired": set(),
    "deleted": set(),
}

DOCUMENT_VERSION_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"queued"},
    "queued": {"extracting"},
    "extracting": {"chunking", "failed"},
    "chunking": {"embedding", "failed"},
    "embedding": {"ready", "failed"},
    "ready": {"superseded"},
    "failed": set(),
    "superseded": set(),
    "withdrawn": set(),
}


@dataclass(frozen=True)
class DocumentTransitionResult:
    document: Document
    previous_status: str
    new_status: str


@dataclass(frozen=True)
class DocumentVersionTransitionResult:
    document_version: DocumentVersion
    previous_status: str
    new_status: str


def _validate_transition(
    *,
    current_status: str,
    new_status: str,
    allowed_transitions: dict[str, set[str]],
) -> None:
    allowed_statuses = allowed_transitions.get(current_status, set())
    if new_status not in allowed_statuses:
        raise InvalidLifecycleTransition(
            f"Invalid lifecycle transition from {current_status!r} to {new_status!r}."
        )


def transition_document_status(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    new_status: str,
    actor_user_id: str | None = None,
) -> DocumentTransitionResult:
    document = get_document_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )
    if document is None:
        raise LifecycleTargetNotFound("Document not found for tenant workspace.")

    previous_status = document.status
    _validate_transition(
        current_status=previous_status,
        new_status=new_status,
        allowed_transitions=DOCUMENT_TRANSITIONS,
    )

    document.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "archived":
        document.archived_at = now
    if new_status == "expired":
        document.expires_at = now
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document.status.transitioned",
        entity_type="document",
        entity_id=document.id,
        document_id=document.id,
        previous_status=previous_status,
        new_status=new_status,
        metadata_json={"status_field": "status"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return DocumentTransitionResult(
        document=document,
        previous_status=previous_status,
        new_status=new_status,
    )


def transition_document_version_status(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    new_status: str,
    processing_error: str | None = None,
    actor_user_id: str | None = None,
) -> DocumentVersionTransitionResult:
    document_version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if document_version is None:
        raise LifecycleTargetNotFound("Document version not found for tenant workspace.")

    previous_status = document_version.processing_status
    _validate_transition(
        current_status=previous_status,
        new_status=new_status,
        allowed_transitions=DOCUMENT_VERSION_TRANSITIONS,
    )

    document_version.processing_status = new_status
    if new_status == "failed":
        document_version.processing_error = processing_error or "Processing failed."
    elif processing_error is not None:
        document_version.processing_error = processing_error
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.processing_status.transitioned",
        entity_type="document_version",
        entity_id=document_version.id,
        document_id=document_id,
        document_version_id=document_version.id,
        previous_status=previous_status,
        new_status=new_status,
        metadata_json={"status_field": "processing_status"},
    )
    db.add(document_version)
    db.commit()
    db.refresh(document_version)
    return DocumentVersionTransitionResult(
        document_version=document_version,
        previous_status=previous_status,
        new_status=new_status,
    )

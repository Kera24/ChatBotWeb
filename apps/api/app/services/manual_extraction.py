from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import DocumentVersion
from app.repositories.audit_repository import add_audit_event
from app.repositories.document_repository import get_document_version_for_workspace
from app.services.local_storage import LocalDocumentStorage
from app.services.text_extraction import extract_text_from_file


class ManualExtractionTargetNotFound(LookupError):
    pass


class InvalidManualExtractionStatus(ValueError):
    pass


@dataclass(frozen=True)
class ManualExtractionResult:
    document_version: DocumentVersion
    success: bool
    previous_status: str
    new_status: str
    extracted_text_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def manually_extract_document_version(
    db: Session,
    *,
    organisation_id: str,
    workspace_id: str,
    document_id: str,
    document_version_id: str,
    storage: LocalDocumentStorage,
    actor_user_id: str | None = None,
) -> ManualExtractionResult:
    version = get_document_version_for_workspace(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        document_id=document_id,
        document_version_id=document_version_id,
    )
    if version is None:
        raise ManualExtractionTargetNotFound("Document version not found for tenant workspace.")

    previous_status = version.processing_status
    if previous_status != "uploaded":
        raise InvalidManualExtractionStatus(
            f"Manual extraction requires processing_status 'uploaded', got {previous_status!r}."
        )

    version.processing_status = "processing"
    db.add(version)
    db.flush()

    if version.original_file_path is None:
        extraction_result = None
        error_code = "ORIGINAL_FILE_MISSING"
        error_message = "Document version does not have an original file path."
    else:
        try:
            original_path = storage.resolve_path(version.original_file_path)
            extraction_result = extract_text_from_file(
                original_path,
                source_type=version.document.source_type,
                storage_root=storage.root_path,
            )
            error_code = extraction_result.error.code if extraction_result.error is not None else None
            error_message = extraction_result.error.message if extraction_result.error is not None else None
        except ValueError:
            extraction_result = None
            error_code = "FILE_OUTSIDE_STORAGE_ROOT"
            error_message = "Extraction file path is outside the configured storage root."

    if extraction_result is not None and extraction_result.success:
        extracted_text_path = storage.save_extracted_text(
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            document_id=document_id,
            document_version_id=document_version_id,
            text=extraction_result.text,
        )
        version.extracted_text_path = extracted_text_path
        version.processing_status = "ready"
        version.processing_error = None
        metadata_json = dict(version.metadata_json or {})
        metadata_json["extraction"] = {
            "text_length": len(extraction_result.text),
            "parser": extraction_result.metadata.get("parser"),
        }
        version.metadata_json = metadata_json
        add_audit_event(
            db,
            organisation_id=organisation_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="document_version.extraction.succeeded",
            entity_type="document_version",
            entity_id=version.id,
            document_id=document_id,
            document_version_id=version.id,
            previous_status=previous_status,
            new_status="ready",
            metadata_json={"extracted_text_path": extracted_text_path},
        )
        db.commit()
        db.refresh(version)
        return ManualExtractionResult(
            document_version=version,
            success=True,
            previous_status=previous_status,
            new_status="ready",
            extracted_text_path=extracted_text_path,
        )

    version.processing_status = "failed"
    version.processing_error = error_message or "Text extraction failed for this document."
    metadata_json = dict(version.metadata_json or {})
    metadata_json["extraction"] = {"error_code": error_code or "EXTRACTION_FAILED"}
    version.metadata_json = metadata_json
    add_audit_event(
        db,
        organisation_id=organisation_id,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="document_version.extraction.failed",
        entity_type="document_version",
        entity_id=version.id,
        document_id=document_id,
        document_version_id=version.id,
        previous_status=previous_status,
        new_status="failed",
        metadata_json={"error_code": error_code or "EXTRACTION_FAILED"},
    )
    db.commit()
    db.refresh(version)
    return ManualExtractionResult(
        document_version=version,
        success=False,
        previous_status=previous_status,
        new_status="failed",
        error_code=error_code or "EXTRACTION_FAILED",
        error_message=version.processing_error,
    )

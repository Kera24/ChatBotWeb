from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from re import sub
from uuid import uuid4


SUPPORTED_UPLOAD_TYPES: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".csv": "csv",
}


class UnsupportedUploadType(ValueError):
    pass


class UploadTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    relative_path: str
    absolute_path: str
    source_type: str
    content_type: str | None
    size_bytes: int
    checksum: str


class LocalDocumentStorage:
    def __init__(self, *, root_path: str, max_upload_bytes: int) -> None:
        self.root_path = Path(root_path)
        self.max_upload_bytes = max_upload_bytes

    def save_upload(
        self,
        *,
        organisation_id: str,
        workspace_id: str,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> StoredUpload:
        source_type = self._source_type_for_filename(filename)
        size_bytes = len(content)
        if size_bytes > self.max_upload_bytes:
            raise UploadTooLarge("Uploaded file exceeds the configured maximum size.")

        safe_filename = self._safe_filename(filename)
        relative_path = str(
            Path(organisation_id)
            / workspace_id
            / f"{uuid4()}-{safe_filename}"
        )
        absolute_path = self.root_path / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)

        return StoredUpload(
            original_filename=filename,
            relative_path=relative_path.replace("\\", "/"),
            absolute_path=str(absolute_path),
            source_type=source_type,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=sha256(content).hexdigest(),
        )


    def resolve_path(self, relative_path: str) -> Path:
        root = self.root_path.resolve(strict=False)
        resolved = (self.root_path / relative_path).resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("Storage path is outside the configured root.") from exc
        return resolved

    def save_extracted_text(
        self,
        *,
        organisation_id: str,
        workspace_id: str,
        document_id: str,
        document_version_id: str,
        text: str,
    ) -> str:
        relative_path = str(
            Path(organisation_id)
            / workspace_id
            / "extracted"
            / f"{document_id}-{document_version_id}.txt"
        )
        absolute_path = self.root_path / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(text, encoding="utf-8")
        return relative_path.replace("\\", "/")

    def delete(self, relative_path: str) -> None:
        path = self.root_path / relative_path
        if path.exists() and path.is_file():
            path.unlink()

    @staticmethod
    def _source_type_for_filename(filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        source_type = SUPPORTED_UPLOAD_TYPES.get(suffix)
        if source_type is None:
            raise UnsupportedUploadType("Unsupported file type. Supported types: PDF, DOCX, TXT, CSV.")
        return source_type

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "upload"
        return sub(r"[^A-Za-z0-9._-]", "_", name)

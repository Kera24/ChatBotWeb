import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from docx import Document as DocxDocument
from pypdf import PdfReader


SUPPORTED_EXTRACTION_TYPES = {"txt", "csv", "pdf", "docx"}


@dataclass(frozen=True)
class ExtractionError:
    code: str
    message: str


@dataclass(frozen=True)
class ExtractionResult:
    success: bool
    source_type: str
    text: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    error: ExtractionError | None = None


def extract_text_from_file(
    file_path: str | Path,
    *,
    source_type: str,
    storage_root: str | Path | None = None,
) -> ExtractionResult:
    normalized_source_type = source_type.lower().strip()
    if normalized_source_type not in SUPPORTED_EXTRACTION_TYPES:
        return _failure(
            normalized_source_type,
            "UNSUPPORTED_SOURCE_TYPE",
            "Unsupported extraction source type.",
        )

    try:
        resolved_path = Path(file_path).resolve(strict=False)
        if storage_root is not None:
            resolved_root = Path(storage_root).resolve(strict=False)
            if not _is_relative_to(resolved_path, resolved_root):
                return _failure(
                    normalized_source_type,
                    "FILE_OUTSIDE_STORAGE_ROOT",
                    "Extraction file path is outside the configured storage root.",
                )

        if not resolved_path.is_file():
            return _failure(
                normalized_source_type,
                "FILE_NOT_FOUND",
                "Extraction file does not exist.",
            )

        extractor = _extractors()[normalized_source_type]
        text, metadata = extractor(resolved_path)
        return ExtractionResult(
            success=True,
            source_type=normalized_source_type,
            text=text,
            metadata={"path": str(resolved_path), **metadata},
        )
    except Exception:
        return _failure(
            normalized_source_type,
            "EXTRACTION_FAILED",
            "Text extraction failed for this document.",
        )


def _extractors() -> dict[str, Callable[[Path], tuple[str, dict[str, object]]]]:
    return {
        "txt": _extract_txt,
        "csv": _extract_csv,
        "pdf": _extract_pdf,
        "docx": _extract_docx,
    }


def _extract_txt(path: Path) -> tuple[str, dict[str, object]]:
    return path.read_text(encoding="utf-8-sig", errors="replace"), {"parser": "utf-8-text"}


def _extract_csv(path: Path) -> tuple[str, dict[str, object]]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            rows.append(", ".join(cell.strip() for cell in row))
    return "\n".join(rows), {"parser": "python-csv", "row_count": len(rows)}


def _extract_pdf(path: Path) -> tuple[str, dict[str, object]]:
    reader = PdfReader(str(path))
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(text for text in page_text if text)
    return text, {"parser": "pypdf", "page_count": len(reader.pages)}


def _extract_docx(path: Path) -> tuple[str, dict[str, object]]:
    document = DocxDocument(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs), {"parser": "python-docx", "paragraph_count": len(paragraphs)}


def _failure(source_type: str, code: str, message: str) -> ExtractionResult:
    return ExtractionResult(
        success=False,
        source_type=source_type,
        error=ExtractionError(code=code, message=message),
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

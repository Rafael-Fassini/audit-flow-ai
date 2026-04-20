from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


SUPPORTED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".txt"})


class UnsupportedDocumentTypeError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


class DocumentTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class StoredInputFile:
    document_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_path: Path


class LocalInputFileStorage:
    def __init__(self, storage_dir: Path, max_size_bytes: int) -> None:
        self._storage_dir = storage_dir
        self._max_size_bytes = max_size_bytes

    def store(self, filename: str, content_type: str, content: bytes) -> StoredInputFile:
        normalized_filename = self._safe_filename(filename)
        self._validate(normalized_filename, content)

        document_id = str(uuid4())
        document_dir = self._storage_dir / document_id
        document_dir.mkdir(parents=True, exist_ok=False)

        storage_path = document_dir / normalized_filename
        storage_path.write_bytes(content)

        return StoredInputFile(
            document_id=document_id,
            original_filename=normalized_filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=storage_path,
        )

    def _validate(self, filename: str, content: bytes) -> None:
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                "Supported document types are PDF, DOCX, and TXT."
            )
        if not content:
            raise EmptyDocumentError("Uploaded document cannot be empty.")
        if len(content) > self._max_size_bytes:
            raise DocumentTooLargeError("Uploaded document exceeds the size limit.")

    def _safe_filename(self, filename: str) -> str:
        safe_name = Path(filename).name.strip()
        return safe_name or "document"

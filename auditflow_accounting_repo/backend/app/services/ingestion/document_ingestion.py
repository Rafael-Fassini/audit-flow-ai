from datetime import datetime, timezone

from app.models.document import DocumentMetadata, DocumentStatus
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion.storage import LocalInputFileStorage


class DocumentIngestionService:
    def __init__(
        self,
        storage: LocalInputFileStorage,
        repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._repository = repository

    def ingest(
        self,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentMetadata:
        stored_file = self._storage.store(
            filename=filename,
            content_type=content_type or "application/octet-stream",
            content=content,
        )

        document = DocumentMetadata(
            id=stored_file.document_id,
            original_filename=stored_file.original_filename,
            content_type=stored_file.content_type,
            size_bytes=stored_file.size_bytes,
            storage_path=stored_file.storage_path,
            status=DocumentStatus.STORED,
            created_at=datetime.now(timezone.utc),
        )
        return self._repository.save(document)

from app.repositories.document_repository import JsonDocumentRepository
from app.services.ingestion.document_ingestion import DocumentIngestionService
from app.services.ingestion.storage import (
    LocalInputFileStorage,
    UnsupportedDocumentTypeError,
)


def test_ingestion_stores_raw_file_and_metadata(tmp_path) -> None:
    storage_dir = tmp_path / "uploads"
    metadata_path = tmp_path / "document_metadata.json"
    service = DocumentIngestionService(
        storage=LocalInputFileStorage(storage_dir=storage_dir, max_size_bytes=1024),
        repository=JsonDocumentRepository(metadata_path),
    )

    document = service.ingest(
        filename="walkthrough.txt",
        content_type="text/plain",
        content=b"accounting process notes",
    )

    assert document.status == "stored"
    assert document.original_filename == "walkthrough.txt"
    assert document.size_bytes == len(b"accounting process notes")
    assert document.storage_path.exists()
    assert document.storage_path.read_bytes() == b"accounting process notes"

    repository = JsonDocumentRepository(metadata_path)
    persisted = repository.get(document.id)

    assert persisted is not None
    assert persisted.id == document.id
    assert persisted.storage_path == document.storage_path


def test_ingestion_rejects_unsupported_document_type(tmp_path) -> None:
    service = DocumentIngestionService(
        storage=LocalInputFileStorage(
            storage_dir=tmp_path / "uploads",
            max_size_bytes=1024,
        ),
        repository=JsonDocumentRepository(tmp_path / "document_metadata.json"),
    )

    try:
        service.ingest(
            filename="ledger.csv",
            content_type="text/csv",
            content=b"not supported yet",
        )
    except UnsupportedDocumentTypeError:
        return

    raise AssertionError("Expected unsupported document type to be rejected.")

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.documents import get_document_ingestion_service
from app.main import create_app
from app.repositories.document_repository import JsonDocumentRepository
from app.services.ingestion.document_ingestion import DocumentIngestionService
from app.services.ingestion.storage import LocalInputFileStorage


@pytest.mark.anyio
async def test_upload_document_returns_stored_document_metadata(tmp_path) -> None:
    metadata_path = tmp_path / "document_metadata.json"
    app = create_app()
    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=1024,
            ),
            repository=JsonDocumentRepository(metadata_path),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/documents/",
            files={
                "file": (
                    "process.txt",
                    b"documented posting logic",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"]
    assert payload["filename"] == "process.txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"documented posting logic")
    assert payload["status"] == "stored"

    persisted = JsonDocumentRepository(metadata_path).get(payload["id"])
    assert persisted is not None
    assert persisted.storage_path.exists()


@pytest.mark.anyio
async def test_upload_document_rejects_unsupported_file_type(tmp_path) -> None:
    app = create_app()
    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=1024,
            ),
            repository=JsonDocumentRepository(tmp_path / "document_metadata.json"),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/documents/",
            files={"file": ("entries.csv", b"date,account", "text/csv")},
        )

    assert response.status_code == 415
    assert response.json()["detail"] == "Supported document types are PDF, DOCX, and TXT."

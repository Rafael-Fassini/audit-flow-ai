from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.models.document import DocumentMetadata
from app.repositories.document_repository import JsonDocumentRepository
from app.schemas.document import DocumentUploadResponse
from app.services.ingestion.document_ingestion import DocumentIngestionService
from app.services.ingestion.storage import (
    DocumentTooLargeError,
    EmptyDocumentError,
    LocalInputFileStorage,
    UnsupportedDocumentTypeError,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@dataclass(frozen=True)
class UploadedDocument:
    filename: str
    content_type: str | None
    content: bytes


async def get_document_ingestion_service() -> DocumentIngestionService:
    storage = LocalInputFileStorage(
        storage_dir=settings.upload_storage_dir,
        max_size_bytes=settings.max_upload_size_bytes,
    )
    repository = JsonDocumentRepository(settings.document_metadata_path)
    return DocumentIngestionService(storage=storage, repository=repository)


@router.post(
    "/",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    ingestion_service: DocumentIngestionService = Depends(
        get_document_ingestion_service
    ),
) -> DocumentUploadResponse:
    uploaded_document = await _extract_uploaded_document(request)
    try:
        document = ingestion_service.ingest(
            filename=uploaded_document.filename,
            content_type=uploaded_document.content_type,
            content=uploaded_document.content,
        )
    except UnsupportedDocumentTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except EmptyDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DocumentTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

    return _to_upload_response(document)


def _to_upload_response(document: DocumentMetadata) -> DocumentUploadResponse:
    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        status=str(document.status),
        created_at=document.created_at,
    )


async def _extract_uploaded_document(request: Request) -> UploadedDocument:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document upload must use multipart/form-data.",
        )

    body = await request.body()
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: "
        + content_type.encode("utf-8")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body
    )

    for part in message.iter_parts():
        content_disposition = part.get_content_disposition()
        field_name = part.get_param("name", header="content-disposition")
        if content_disposition != "form-data" or field_name != "file":
            continue

        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if filename is None or payload is None:
            break

        return UploadedDocument(
            filename=filename,
            content_type=part.get_content_type(),
            content=payload,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Multipart request must include a file field.",
    )

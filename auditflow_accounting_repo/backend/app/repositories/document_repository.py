import json
from pathlib import Path

from app.models.document import DocumentMetadata


class DocumentRepository:
    def save(self, document: DocumentMetadata) -> DocumentMetadata:
        raise NotImplementedError

    def get(self, document_id: str) -> DocumentMetadata | None:
        raise NotImplementedError


class JsonDocumentRepository(DocumentRepository):
    def __init__(self, metadata_path: Path) -> None:
        self._metadata_path = metadata_path

    def save(self, document: DocumentMetadata) -> DocumentMetadata:
        records = self._load_records()
        records[document.id] = document.model_dump(mode="json")
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path.write_text(
            json.dumps(records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return document

    def get(self, document_id: str) -> DocumentMetadata | None:
        record = self._load_records().get(document_id)
        if record is None:
            return None
        return DocumentMetadata.model_validate(record)

    def _load_records(self) -> dict[str, dict[str, object]]:
        if not self._metadata_path.exists():
            return {}

        content = self._metadata_path.read_text(encoding="utf-8").strip()
        if not content:
            return {}

        records = json.loads(content)
        if not isinstance(records, dict):
            return {}
        return records

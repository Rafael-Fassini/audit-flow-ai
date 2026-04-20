from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(str, Enum):
    STORED = "stored"


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    original_filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    storage_path: Path
    status: DocumentStatus
    created_at: datetime

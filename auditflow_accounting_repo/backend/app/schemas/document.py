from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    status: str
    created_at: datetime

from enum import Enum

from pydantic import BaseModel, Field


class DocumentFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class DocumentSection(BaseModel):
    index: int = Field(ge=0)
    title: str | None = None
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class DocumentChunk(BaseModel):
    index: int = Field(ge=0)
    section_index: int = Field(ge=0)
    title: str | None = None
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class ParsedDocument(BaseModel):
    filename: str
    document_format: DocumentFormat
    text: str = Field(min_length=1)


class ChunkedDocument(BaseModel):
    filename: str
    document_format: DocumentFormat
    text: str = Field(min_length=1)
    sections: list[DocumentSection]
    chunks: list[DocumentChunk]

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetails(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["Request validation failed."])
    request_id: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    detail: Any
    error: ErrorDetails

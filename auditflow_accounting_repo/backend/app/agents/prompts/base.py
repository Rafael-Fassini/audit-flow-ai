from typing import Literal

from pydantic import BaseModel, Field


class PromptMessage(BaseModel):
    role: Literal["system", "user"]
    content: str = Field(min_length=1)


class PromptPayload(BaseModel):
    messages: list[PromptMessage] = Field(min_length=1)
    response_schema: str = Field(min_length=1)


def schema_instruction(schema_name: str) -> str:
    return (
        f"Return only JSON that validates against the {schema_name} schema. "
        "Do not include markdown, commentary, or fields outside the schema."
    )

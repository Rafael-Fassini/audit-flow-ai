from enum import Enum

from pydantic import BaseModel, Field


class KnowledgeCategory(str, Enum):
    ACCOUNTING_POLICY = "accounting_policy"
    CHART_OF_ACCOUNTS = "chart_of_accounts"
    POSTING_GUIDANCE = "posting_guidance"
    CONTROL_GUIDANCE = "control_guidance"
    INCONSISTENCY_PATTERN = "inconsistency_pattern"


class KnowledgeSnippet(BaseModel):
    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    category: KnowledgeCategory
    tags: list[str] = Field(default_factory=list)


class KnowledgeDocument(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    category: KnowledgeCategory
    snippets: list[KnowledgeSnippet] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    snippet: KnowledgeSnippet
    score: float = Field(ge=0.0, le=1.0)

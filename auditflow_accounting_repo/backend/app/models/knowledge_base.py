from enum import Enum

from pydantic import BaseModel, Field, model_validator


class KnowledgeCategory(str, Enum):
    ACCOUNTING_POLICY = "accounting_policy"
    CHART_OF_ACCOUNTS = "chart_of_accounts"
    POSTING_GUIDANCE = "posting_guidance"
    CONTROL_GUIDANCE = "control_guidance"
    INCONSISTENCY_PATTERN = "inconsistency_pattern"


class DocumentFamily(str, Enum):
    DERE = "dere"
    REFORMA_TRIBUTARIA = "reforma_tributaria"
    SOCIETARIO_GERAL = "societario_geral"
    OUTRO = "outro"


class DocumentScope(str, Enum):
    REGIME_ESPECIFICO = "regime_especifico"
    NORMA_GERAL = "norma_geral"
    SOCIETARIO_GERAL = "societario_geral"


class AuthorityLevel(str, Enum):
    LEI = "lei"
    MANUAL = "manual"
    LEIAUTE = "leiaute"
    TABELA = "tabela"
    REGRA_VALIDACAO = "regra_validacao"
    PDF_AUXILIAR = "pdf_auxiliar"


class RegimeApplicability(str, Enum):
    GERAL = "geral"
    SERV_FIN = "serv_fin"
    SAUDE = "saude"
    PROGNOSTICOS = "prognosticos"


class KnowledgeSnippet(BaseModel):
    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    category: KnowledgeCategory
    tags: list[str] = Field(default_factory=list)
    source_file: str = ""
    source_archive: str = ""
    document_family: DocumentFamily = DocumentFamily.OUTRO
    document_scope: DocumentScope = DocumentScope.NORMA_GERAL
    authority_level: AuthorityLevel = AuthorityLevel.PDF_AUXILIAR
    regime_applicability: RegimeApplicability = RegimeApplicability.GERAL
    chunk_id: str = ""
    raw_text: str = ""

    @model_validator(mode="after")
    def default_chunk_metadata(self) -> "KnowledgeSnippet":
        if not self.chunk_id:
            self.chunk_id = self.id
        if not self.raw_text:
            self.raw_text = self.text
        return self


class KnowledgeDocument(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    category: KnowledgeCategory
    snippets: list[KnowledgeSnippet] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    snippet: KnowledgeSnippet
    score: float = Field(ge=0.0, le=1.0)

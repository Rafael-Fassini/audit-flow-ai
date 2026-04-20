from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.accounting_process import AccountingProcess
from app.models.document_section import ChunkedDocument, ParsedDocument
from app.models.knowledge_base import RetrievalResult
from app.models.report import AnalysisReport
from app.models.risk import RiskInferenceResult


AGENT_OUTPUT_CONTRACT_VERSION = "agent-output.v1"


class AgentRole(str, Enum):
    DOCUMENT_LOADER = "document_loader"
    DOCUMENT_PARSER = "document_parser"
    DOCUMENT_CHUNKER = "document_chunker"
    PROCESS_STRUCTURER = "process_structurer"
    KNOWLEDGE_RETRIEVER = "knowledge_retriever"
    RISK_INFERENCE = "risk_inference"
    REPORT_ASSEMBLER = "report_assembler"


class AgentOutputStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class AgentError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False


class AgentOutputMetadata(BaseModel):
    contract_version: Literal["agent-output.v1"] = AGENT_OUTPUT_CONTRACT_VERSION
    agent_role: AgentRole
    status: AgentOutputStatus = AgentOutputStatus.COMPLETED
    analysis_id: str | None = None
    document_id: str | None = None
    source_filename: str | None = None
    errors: list[AgentError] = Field(default_factory=list)

    @model_validator(mode="after")
    def failed_outputs_include_errors(self) -> "AgentOutputMetadata":
        if self.status == AgentOutputStatus.FAILED and not self.errors:
            raise ValueError("failed agent outputs must include at least one error")
        return self


class DocumentLoaderAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    filename: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class DocumentParserAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    parsed_document: ParsedDocument


class DocumentChunkerAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    chunked_document: ChunkedDocument


class ProcessStructurerAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    process: AccountingProcess


class KnowledgeRetrieverAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    retrieved_context: list[RetrievalResult] = Field(default_factory=list)


class RiskInferenceAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    risk_result: RiskInferenceResult


class ReportAssemblerAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    report: AnalysisReport

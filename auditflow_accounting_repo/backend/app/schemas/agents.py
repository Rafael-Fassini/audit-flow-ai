from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.accounting_process import AccountingProcess
from app.models.document import DocumentMetadata
from app.models.document_section import ChunkedDocument, ParsedDocument
from app.models.knowledge_base import RetrievalResult
from app.models.report import AnalysisReport
from app.models.risk import RiskInferenceResult


AGENT_OUTPUT_CONTRACT_VERSION = "agent-output.v1"


class AgentRole(str, Enum):
    DOCUMENT_LOADER = "document_loader"
    DOCUMENT_PARSER = "document_parser"
    DOCUMENT_CHUNKER = "document_chunker"
    DOCUMENT_UNDERSTANDING = "document_understanding"
    RED_FLAG = "red_flag"
    ACCOUNTING_AUDIT = "accounting_audit"
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


class DocumentUnderstandingStep(BaseModel):
    index: int = Field(ge=0)
    description: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class DocumentUnderstandingEntity(BaseModel):
    value: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class DocumentUnderstandingResult(BaseModel):
    process_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    steps: list[DocumentUnderstandingStep] = Field(default_factory=list)
    controls: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    actors: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    values: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    dates: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    approvals: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    payments: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    account_references: list[DocumentUnderstandingEntity] = Field(default_factory=list)
    cost_center_references: list[DocumentUnderstandingEntity] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def step_indexes_are_sequential(self) -> "DocumentUnderstandingResult":
        expected = list(range(len(self.steps)))
        actual = [step.index for step in self.steps]
        if actual != expected:
            raise ValueError("document understanding step indexes must be sequential")
        return self


class DocumentUnderstandingAgentInput(BaseModel):
    parsed_document: ParsedDocument
    document_metadata: DocumentMetadata
    analysis_id: str | None = None


class DocumentUnderstandingAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    understanding: DocumentUnderstandingResult


class RedFlagType(str, Enum):
    IMPOSSIBLE_DATE = "impossible_date"
    CONFLICTING_VALUES = "conflicting_values"
    MISSING_PROCUREMENT_ARTIFACTS = "missing_procurement_artifacts"
    INFORMAL_APPROVAL = "informal_approval"
    PAYMENT_BEFORE_INVOICE = "payment_before_invoice"
    PAYMENT_TO_PERSONAL_OR_THIRD_PARTY_ACCOUNT = (
        "payment_to_personal_or_third_party_account"
    )
    INFORMAL_PAYMENT_INSTRUCTIONS = "informal_payment_instructions"
    URGENCY_OVERRIDE_WITHOUT_SUPPORT = "urgency_override_without_support"


class RedFlagSeverity(str, Enum):
    MEDIUM = "medium"
    HIGH = "high"


class RedFlagEvidence(BaseModel):
    text: str = Field(min_length=1)
    source: Literal["document"] = "document"


class RedFlagCandidateFinding(BaseModel):
    id: str = Field(min_length=1)
    red_flag_type: RedFlagType
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: RedFlagSeverity
    evidence: list[RedFlagEvidence] = Field(min_length=1)


class RedFlagAgentInput(BaseModel):
    parsed_document: ParsedDocument
    document_metadata: DocumentMetadata
    understanding: DocumentUnderstandingResult | None = None
    analysis_id: str | None = None


class RedFlagAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    findings: list[RedFlagCandidateFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_red_flag_output(self) -> "RedFlagAgentOutput":
        if self.metadata.agent_role != AgentRole.RED_FLAG:
            raise ValueError("red flag output metadata must use red_flag agent role")
        finding_ids = [finding.id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("red flag finding ids must be unique")
        return self


class AccountingAuditCategory(str, Enum):
    DOCUMENTARY_GAP = "documentary_gap"
    CONTROL_GAP = "control_gap"
    TRACEABILITY_GAP = "traceability_gap"
    RECONCILIATION_GAP = "reconciliation_gap"
    COST_CENTER_INCONSISTENCY = "cost_center_inconsistency"
    APPROVAL_WEAKNESS = "approval_weakness"
    POSTING_INCONSISTENCY = "posting_inconsistency"


class AccountingAuditSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AccountingAuditEvidence(BaseModel):
    text: str = Field(min_length=1)
    source: Literal["document"] = "document"


class AccountingAuditCandidateFinding(BaseModel):
    id: str = Field(min_length=1)
    category: AccountingAuditCategory
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: AccountingAuditSeverity
    evidence: list[AccountingAuditEvidence] = Field(min_length=1)
    account_references: list[str] = Field(default_factory=list)
    cost_center_references: list[str] = Field(default_factory=list)


class AccountingAuditAgentInput(BaseModel):
    parsed_document: ParsedDocument
    document_metadata: DocumentMetadata
    understanding: DocumentUnderstandingResult | None = None
    analysis_id: str | None = None


class AccountingAuditAgentOutput(BaseModel):
    metadata: AgentOutputMetadata
    findings: list[AccountingAuditCandidateFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_accounting_audit_output(self) -> "AccountingAuditAgentOutput":
        if self.metadata.agent_role != AgentRole.ACCOUNTING_AUDIT:
            raise ValueError(
                "accounting audit output metadata must use accounting_audit agent role"
            )
        finding_ids = [finding.id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("accounting audit finding ids must be unique")
        return self


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

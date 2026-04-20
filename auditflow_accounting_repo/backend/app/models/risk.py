from enum import Enum

from pydantic import BaseModel, Field

from app.models.accounting_process import EvidenceSnippet


class FindingSource(str, Enum):
    HEURISTIC = "heuristic"
    LLM = "llm"
    HYBRID = "hybrid"


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InconsistencyType(str, Enum):
    ACCOUNT_USAGE = "account_usage"
    POSTING_LOGIC = "posting_logic"
    DOCUMENTARY_GAP = "documentary_gap"
    CONTROL_GAP = "control_gap"
    RECONCILIATION_GAP = "reconciliation_gap"
    TRACEABILITY_GAP = "traceability_gap"
    THIRD_PARTY_DEPENDENCY = "third_party_dependency"
    CLASSIFICATION = "classification"


class RiskCategory(str, Enum):
    MISCLASSIFICATION = "misclassification"
    INSUFFICIENT_SUPPORT = "insufficient_support"
    WEAK_CONTROL = "weak_control"
    GENERIC_ACCOUNT_OVERUSE = "generic_account_overuse"


class FindingEvidence(BaseModel):
    source: str = Field(min_length=1)
    text: str = Field(min_length=1)
    section_index: int | None = Field(default=None, ge=0)
    chunk_index: int | None = Field(default=None, ge=0)
    knowledge_chunk_id: str | None = None
    document_family: str | None = None
    document_scope: str | None = None


class Inconsistency(BaseModel):
    id: str = Field(min_length=1)
    type: InconsistencyType
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: FindingSource
    severity_hint: FindingSeverity
    confidence_hint: float = Field(ge=0.0, le=1.0)
    evidence: list[FindingEvidence] = Field(default_factory=list)


class RiskItem(BaseModel):
    id: str = Field(min_length=1)
    category: RiskCategory
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: FindingSource
    severity_hint: FindingSeverity
    confidence_hint: float = Field(ge=0.0, le=1.0)
    related_inconsistency_ids: list[str] = Field(default_factory=list)
    evidence: list[FindingEvidence] = Field(default_factory=list)


class FollowUpQuestion(BaseModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    related_finding_ids: list[str] = Field(default_factory=list)


class RiskInferenceResult(BaseModel):
    inconsistencies: list[Inconsistency] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)


def evidence_from_process(
    evidence: EvidenceSnippet,
    source: str = "process",
) -> FindingEvidence:
    return FindingEvidence(
        source=source,
        text=evidence.text,
        section_index=evidence.section_index,
        chunk_index=evidence.chunk_index,
    )

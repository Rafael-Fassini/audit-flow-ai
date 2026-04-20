from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.accounting_process import AccountingProcess
from app.models.risk import FindingEvidence, FollowUpQuestion


class AnalysisStatus(str, Enum):
    COMPLETED = "completed"


class FindingScore(BaseModel):
    severity: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool


class ReportFinding(BaseModel):
    id: str = Field(min_length=1)
    finding_type: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)
    score: FindingScore
    related_finding_ids: list[str] = Field(default_factory=list)
    evidence: list[FindingEvidence] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    process_name: str = Field(min_length=1)
    source_filename: str = Field(min_length=1)
    total_findings: int = Field(ge=0)
    high_severity_findings: int = Field(ge=0)
    review_required_count: int = Field(ge=0)


class AnalysisReport(BaseModel):
    analysis_id: str = Field(min_length=1)
    status: AnalysisStatus
    generated_at: datetime
    summary: AnalysisSummary
    process: AccountingProcess
    findings: list[ReportFinding] = Field(default_factory=list)
    evidence: list[FindingEvidence] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)

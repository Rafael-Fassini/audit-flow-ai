from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.models.accounting_process import AccountingProcess
from app.models.risk import FindingEvidence, FollowUpQuestion


class AnalysisStatus(str, Enum):
    COMPLETED = "completed"


class ScopedConclusion(str, Enum):
    YES = "YES"
    NO = "NO"
    INDETERMINATE_HUMAN_REVIEW_REQUIRED = "INDETERMINATE / HUMAN REVIEW REQUIRED"


SCOPED_ANALYSIS_QUESTION = (
    "Does this document present relevant inconsistencies in documentation, approval, "
    "value, classification, or minimum adherence to the defined normative scope?"
)


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


class ScopedConclusionEvidence(BaseModel):
    finding_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    evidence_text: str = Field(min_length=1)


class FinalResponseFinding(BaseModel):
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class FinalResponse(BaseModel):
    conclusion: ScopedConclusion
    top_findings: list[FinalResponseFinding] = Field(default_factory=list, max_length=5)
    missing_items: list[str] = Field(default_factory=list, max_length=5)
    normative_rationale: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)

    @classmethod
    def from_analysis(
        cls,
        scoped_answer: "ScopedQuestionAnswer",
        findings: list[ReportFinding],
        follow_up_questions: list[FollowUpQuestion],
    ) -> "FinalResponse":
        return cls(
            conclusion=scoped_answer.conclusion,
            top_findings=cls._top_findings(findings),
            missing_items=cls._missing_items(findings, follow_up_questions),
            normative_rationale=cls._normative_rationale(scoped_answer.conclusion),
            recommended_action=cls._recommended_action(scoped_answer.conclusion),
        )

    @classmethod
    def _top_findings(cls, findings: list[ReportFinding]) -> list[FinalResponseFinding]:
        evidence_backed = [
            finding
            for finding in findings
            if finding.evidence and finding.category != "out_of_scope"
        ]
        ordered = sorted(
            evidence_backed,
            key=lambda finding: (
                cls._severity_rank(finding.score.severity),
                finding.score.confidence,
            ),
            reverse=True,
        )
        return [
            FinalResponseFinding(
                title=finding.title,
                category=finding.category,
                severity=finding.score.severity,
                evidence=finding.evidence[0].text[:180],
            )
            for finding in ordered[:5]
        ]

    @classmethod
    def _missing_items(
        cls,
        findings: list[ReportFinding],
        follow_up_questions: list[FollowUpQuestion],
    ) -> list[str]:
        missing: list[str] = []
        for finding in findings:
            text = f"{finding.title} {finding.description}".lower()
            if finding.category == "documentary_gap" or any(
                term in text
                for term in (
                    "missing",
                    "not documented",
                    "not provided",
                    "without",
                    "no ",
                    "ausência",
                    "ausencia",
                    "sem ",
                    "não documentado",
                    "nao documentado",
                )
            ):
                missing.append(finding.title)
        for question in follow_up_questions:
            missing.append(question.question)
        return cls._dedupe_text(missing)[:5]

    @staticmethod
    def _normative_rationale(conclusion: ScopedConclusion) -> str:
        if conclusion == ScopedConclusion.NO:
            return (
                "No evidence in the document indicated a scoped issue under the "
                "approved NBC TG / CPC 00 (R2) and LC 214/2025 focus."
            )
        if conclusion == ScopedConclusion.INDETERMINATE_HUMAN_REVIEW_REQUIRED:
            return (
                "The document cannot be concluded on safely within the approved "
                "NBC TG / CPC 00 (R2) and LC 214/2025 scope without human review."
            )
        return (
            "The cited evidence indicates a scoped documentation, approval, value, "
            "classification, or support issue under the approved NBC TG / CPC 00 "
            "(R2) and LC 214/2025 focus."
        )

    @staticmethod
    def _recommended_action(conclusion: ScopedConclusion) -> str:
        if conclusion == ScopedConclusion.NO:
            return "No action required beyond normal retention of the support package."
        if conclusion == ScopedConclusion.INDETERMINATE_HUMAN_REVIEW_REQUIRED:
            return "Route to a human reviewer and request the missing support before relying on the result."
        return "Review the top findings, obtain missing support, and resolve the cited inconsistencies before approval or posting."

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(severity.lower(), 0)

    @staticmethod
    def _dedupe_text(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = " ".join(value.split())
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped


def default_final_response() -> FinalResponse:
    return FinalResponse.from_analysis(
        scoped_answer=default_scoped_answer(),
        findings=[],
        follow_up_questions=[],
    )


class ScopedQuestionAnswer(BaseModel):
    question: str = SCOPED_ANALYSIS_QUESTION
    conclusion: ScopedConclusion
    rationale: str = Field(min_length=1)
    top_findings: list[ScopedConclusionEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_for_yes(self) -> "ScopedQuestionAnswer":
        if self.conclusion == ScopedConclusion.YES and not self.top_findings:
            raise ValueError("YES scoped conclusions require evidence-backed findings")
        return self

    @classmethod
    def from_findings(cls, findings: list[ReportFinding]) -> "ScopedQuestionAnswer":
        evidence_backed = [
            finding
            for finding in findings
            if finding.evidence and finding.category != "out_of_scope"
        ]
        out_of_scope = any(finding.category == "out_of_scope" for finding in findings)
        unsupported_or_review = out_of_scope or any(
            finding.score.review_required and not finding.evidence
            for finding in findings
        )

        if unsupported_or_review:
            return cls(
                conclusion=ScopedConclusion.INDETERMINATE_HUMAN_REVIEW_REQUIRED,
                rationale=(
                    "The scoped question cannot be answered from supported, "
                    "evidence-backed document analysis alone."
                ),
                top_findings=cls._top_finding_evidence(evidence_backed),
            )

        if evidence_backed:
            return cls(
                conclusion=ScopedConclusion.YES,
                rationale=(
                    "The document contains evidence-backed inconsistencies within "
                    "the scoped documentation, approval, value, classification, or "
                    "normative-adherence question."
                ),
                top_findings=cls._top_finding_evidence(evidence_backed),
            )

        return cls(
            conclusion=ScopedConclusion.NO,
            rationale=(
                "No evidence-backed inconsistency was identified within the scoped "
                "documentation, approval, value, classification, or normative-adherence "
                "question."
            ),
        )

    @classmethod
    def _top_finding_evidence(
        cls,
        findings: list[ReportFinding],
    ) -> list[ScopedConclusionEvidence]:
        ordered = sorted(
            findings,
            key=lambda finding: (
                cls._severity_rank(finding.score.severity),
                finding.score.confidence,
            ),
            reverse=True,
        )
        return [
            ScopedConclusionEvidence(
                finding_id=finding.id,
                title=finding.title,
                category=finding.category,
                evidence_text=finding.evidence[0].text[:240],
            )
            for finding in ordered[:5]
            if finding.evidence
        ]

    @staticmethod
    def _severity_rank(severity: str) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(severity.lower(), 0)


def default_scoped_answer() -> ScopedQuestionAnswer:
    return ScopedQuestionAnswer.from_findings([])


class AnalysisReport(BaseModel):
    analysis_id: str = Field(min_length=1)
    status: AnalysisStatus
    generated_at: datetime
    summary: AnalysisSummary
    scoped_answer: ScopedQuestionAnswer = Field(default_factory=default_scoped_answer)
    final_response: FinalResponse = Field(default_factory=default_final_response)
    process: AccountingProcess
    findings: list[ReportFinding] = Field(default_factory=list)
    evidence: list[FindingEvidence] = Field(default_factory=list)
    follow_up_questions: list[FollowUpQuestion] = Field(default_factory=list)

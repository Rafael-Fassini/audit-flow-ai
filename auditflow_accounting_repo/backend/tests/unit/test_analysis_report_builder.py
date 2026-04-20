from app.models.accounting_process import AccountingProcess
from app.models.risk import (
    FindingEvidence,
    FindingSeverity,
    FindingSource,
    FollowUpQuestion,
    Inconsistency,
    InconsistencyType,
    RiskCategory,
    RiskInferenceResult,
    RiskItem,
)
from app.models.report import ScopedConclusion
from app.services.reporting.analysis_report_builder import AnalysisReportBuilder
from app.services.scoring.finding_scorer import FindingScorer


def test_report_builder_generates_stable_structured_payload() -> None:
    report = AnalysisReportBuilder(FindingScorer()).build(
        process=AccountingProcess(
            process_name="Accrual process",
            summary="The team records an accrual.",
            source_filename="walkthrough.txt",
        ),
        risk_result=RiskInferenceResult(
            inconsistencies=[
                Inconsistency(
                    id="inc-1",
                    type=InconsistencyType.POSTING_LOGIC,
                    title="Missing credit",
                    description="Credit side is not clear.",
                    source=FindingSource.HEURISTIC,
                    severity_hint=FindingSeverity.MEDIUM,
                    confidence_hint=0.75,
                    evidence=[FindingEvidence(source="process", text="debit expense")],
                )
            ],
            risks=[
                RiskItem(
                    id="risk-inc-1",
                    category=RiskCategory.MISCLASSIFICATION,
                    title="Posting risk",
                    description="Entry may be incomplete.",
                    source=FindingSource.HEURISTIC,
                    severity_hint=FindingSeverity.MEDIUM,
                    confidence_hint=0.75,
                    related_inconsistency_ids=["inc-1"],
                    evidence=[FindingEvidence(source="process", text="debit expense")],
                )
            ],
            follow_up_questions=[
                FollowUpQuestion(
                    id="q-1",
                    question="What is the credit account?",
                    rationale="Posting side is incomplete.",
                    related_finding_ids=["inc-1"],
                )
            ],
        ),
        analysis_id="analysis-1",
    )

    assert report.analysis_id == "analysis-1"
    assert report.status == "completed"
    assert report.summary.process_name == "Accrual process"
    assert report.summary.total_findings == 2
    assert report.summary.review_required_count == 2
    assert report.scoped_answer.conclusion == ScopedConclusion.YES
    assert report.scoped_answer.top_findings
    assert report.scoped_answer.top_findings[0].evidence_text == "debit expense"
    assert len(report.findings) == 2
    assert len(report.evidence) == 1
    assert report.findings[0].score.severity == "medium"
    assert report.findings[1].related_finding_ids == ["inc-1"]
    assert report.follow_up_questions[0].question == "What is the credit account?"

from datetime import datetime, timezone

from app.agents.report import ReportAgent
from app.models.accounting_process import AccountingProcess
from app.models.report import (
    AnalysisReport,
    AnalysisStatus,
    AnalysisSummary,
)
from app.schemas.agents import (
    AgentOutputMetadata,
    AgentRole,
    ReviewedFinding,
    ReviewerAgentOutput,
    ReviewerEvidence,
    ReviewerFindingKind,
    ReviewerFollowUpQuestion,
    ReviewerSeverity,
    ReviewerSource,
)


def test_report_agent_appends_reviewed_findings_without_mutating_base_report() -> None:
    base_report = _base_report()
    original_payload = base_report.model_dump(mode="json")
    reviewer_output = ReviewerAgentOutput(
        metadata=AgentOutputMetadata(agent_role=AgentRole.REVIEWER),
        operational_findings=[
            ReviewedFinding(
                id="review-control-gap",
                kind=ReviewerFindingKind.OPERATIONAL,
                category="control_gap",
                title="Control gap is documented",
                description="Review control was not performed.",
                severity=ReviewerSeverity.HIGH,
                confidence=0.9,
                review_required=True,
                source_finding_ids=["audit-control-gap"],
                evidence=[
                    ReviewerEvidence(
                        text="The review control was not performed before posting.",
                        source_agent=ReviewerSource.ACCOUNTING_AUDIT,
                        source_finding_id="audit-control-gap",
                    )
                ],
            )
        ],
        follow_up_questions=[
            ReviewerFollowUpQuestion(
                id="follow-up-review-control-gap",
                question="Which review evidence resolves this control gap?",
                rationale="High severity requires confirmation.",
                related_finding_ids=["review-control-gap"],
            )
        ],
    )

    final_report = ReportAgent().build_final_report(base_report, reviewer_output)

    assert base_report.model_dump(mode="json") == original_payload
    assert final_report is not base_report
    assert final_report.summary.total_findings == 1
    assert final_report.summary.high_severity_findings == 1
    assert final_report.summary.review_required_count == 1
    assert final_report.findings[0].id == "agent-review-control-gap"
    assert final_report.findings[0].source == "multi_agent"
    assert final_report.findings[0].evidence[0].text == (
        "The review control was not performed before posting."
    )
    assert final_report.follow_up_questions[0].id == (
        "agent-follow-up-review-control-gap"
    )


def _base_report() -> AnalysisReport:
    return AnalysisReport(
        analysis_id="analysis-1",
        status=AnalysisStatus.COMPLETED,
        generated_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        summary=AnalysisSummary(
            process_name="Accounts payable",
            source_filename="memo.txt",
            total_findings=0,
            high_severity_findings=0,
            review_required_count=0,
        ),
        process=AccountingProcess(
            process_name="Accounts payable",
            summary="Accounts payable memo.",
            source_filename="memo.txt",
        ),
    )

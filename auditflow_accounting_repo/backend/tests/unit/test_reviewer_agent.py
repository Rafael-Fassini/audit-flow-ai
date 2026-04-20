import pytest
from pydantic import ValidationError

from app.agents.reviewer import ReviewerAgent
from app.schemas.agents import (
    AccountingAuditAgentOutput,
    AccountingAuditCandidateFinding,
    AccountingAuditCategory,
    AccountingAuditEvidence,
    AccountingAuditSeverity,
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    RedFlagAgentOutput,
    RedFlagCandidateFinding,
    RedFlagEvidence,
    RedFlagSeverity,
    RedFlagType,
    ReviewedFinding,
    ReviewerAgentInput,
    ReviewerAgentOutput,
    ReviewerEvidence,
    ReviewerFindingKind,
    ReviewerSeverity,
    ReviewerSource,
)


def test_reviewer_merges_semantic_duplicates_and_preserves_evidence() -> None:
    red_flag_output = _red_flag_output()
    accounting_output = _accounting_output()
    original_red_flag_payload = red_flag_output.model_dump(mode="json")
    original_accounting_payload = accounting_output.model_dump(mode="json")

    output = ReviewerAgent().review(
        red_flag_output=red_flag_output,
        accounting_audit_output=accounting_output,
        analysis_id="analysis-1",
    )

    assert output.metadata.agent_role == AgentRole.REVIEWER
    assert output.metadata.status == AgentOutputStatus.COMPLETED
    assert output.metadata.analysis_id == "analysis-1"
    assert output.metadata.document_id == "document-1"
    assert output.metadata.source_filename == "memo.txt"
    assert len(output.operational_findings) == 1
    merged = output.operational_findings[0]
    assert merged.category == "approval_weakness"
    assert merged.severity == ReviewerSeverity.HIGH
    assert merged.confidence >= 0.9
    assert merged.review_required is True
    assert set(merged.source_finding_ids) == {
        "red-informal-approval",
        "audit-approval-weakness",
    }
    assert {
        (evidence.source_agent, evidence.source_finding_id)
        for evidence in merged.evidence
    } == {
        (ReviewerSource.RED_FLAG, "red-informal-approval"),
        (ReviewerSource.ACCOUNTING_AUDIT, "audit-approval-weakness"),
    }
    assert red_flag_output.model_dump(mode="json") == original_red_flag_payload
    assert accounting_output.model_dump(mode="json") == original_accounting_payload


def test_reviewer_separates_documentary_gaps_and_follow_up_questions() -> None:
    output = ReviewerAgent().review(
        red_flag_output=RedFlagAgentOutput(
            metadata=AgentOutputMetadata(agent_role=AgentRole.RED_FLAG),
            findings=[
                RedFlagCandidateFinding(
                    id="red-missing-procurement",
                    red_flag_type=RedFlagType.MISSING_PROCUREMENT_ARTIFACTS,
                    title="Missing procurement artifact is documented",
                    description="Purchase order support is missing.",
                    severity=RedFlagSeverity.HIGH,
                    evidence=[
                        RedFlagEvidence(
                            text="No purchase order was provided for the procurement."
                        )
                    ],
                )
            ],
        ),
        accounting_audit_output=AccountingAuditAgentOutput(
            metadata=AgentOutputMetadata(agent_role=AgentRole.ACCOUNTING_AUDIT),
            findings=[
                AccountingAuditCandidateFinding(
                    id="audit-control-gap",
                    category=AccountingAuditCategory.CONTROL_GAP,
                    title="Control gap is documented",
                    description="Review was not performed.",
                    severity=AccountingAuditSeverity.HIGH,
                    evidence=[
                        AccountingAuditEvidence(
                            text="The review control was not performed before posting."
                        )
                    ],
                )
            ],
        ),
    )

    assert len(output.documentary_gaps) == 1
    assert output.documentary_gaps[0].kind == ReviewerFindingKind.DOCUMENTARY_GAP
    assert output.documentary_gaps[0].category == "documentary_gap"
    assert len(output.operational_findings) == 1
    assert output.operational_findings[0].category == "control_gap"
    assert len(output.follow_up_questions) == 2
    assert any(
        "documentary gap" in question.question.lower()
        for question in output.follow_up_questions
    )


def test_reviewer_propagates_source_review_status() -> None:
    red_flag_output = _red_flag_output()
    red_flag_output = red_flag_output.model_copy(
        deep=True,
        update={
            "metadata": red_flag_output.metadata.model_copy(
                update={
                    "status": AgentOutputStatus.NEEDS_REVIEW,
                    "errors": [
                        AgentError(
                            code="invalid_red_flag_model_output",
                            message="Fallback was used.",
                            retryable=True,
                        )
                    ],
                }
            )
        },
    )

    output = ReviewerAgent().review(red_flag_output=red_flag_output)

    assert output.metadata.status == AgentOutputStatus.NEEDS_REVIEW
    assert output.metadata.errors[0].code == "invalid_red_flag_model_output"


def test_reviewer_schema_validates_role_unique_ids_and_evidence() -> None:
    finding = ReviewedFinding(
        id="finding-1",
        kind=ReviewerFindingKind.OPERATIONAL,
        category="control_gap",
        title="Control gap",
        description="Control was not performed.",
        severity=ReviewerSeverity.HIGH,
        confidence=0.9,
        review_required=True,
        source_finding_ids=["source-1"],
        evidence=[
            ReviewerEvidence(
                text="The control was not performed.",
                source_agent=ReviewerSource.ACCOUNTING_AUDIT,
                source_finding_id="source-1",
            )
        ],
    )

    with pytest.raises(ValidationError):
        ReviewerAgentOutput(
            metadata=AgentOutputMetadata(agent_role=AgentRole.RED_FLAG),
            operational_findings=[],
        )

    with pytest.raises(ValidationError):
        ReviewerAgentOutput(
            metadata=AgentOutputMetadata(agent_role=AgentRole.REVIEWER),
            operational_findings=[finding, finding],
        )

    with pytest.raises(ValidationError):
        ReviewedFinding(
            id="finding-2",
            kind=ReviewerFindingKind.OPERATIONAL,
            category="control_gap",
            title="Control gap",
            description="Control was not performed.",
            severity=ReviewerSeverity.HIGH,
            confidence=1.2,
            review_required=True,
            source_finding_ids=["source-1"],
            evidence=[],
        )


def test_reviewer_input_accepts_candidate_outputs() -> None:
    agent_input = ReviewerAgentInput(
        red_flag_output=_red_flag_output(),
        accounting_audit_output=_accounting_output(),
        analysis_id="analysis-1",
    )

    assert agent_input.red_flag_output is not None
    assert agent_input.accounting_audit_output is not None
    assert agent_input.analysis_id == "analysis-1"


def _red_flag_output() -> RedFlagAgentOutput:
    return RedFlagAgentOutput(
        metadata=AgentOutputMetadata(
            agent_role=AgentRole.RED_FLAG,
            document_id="document-1",
            source_filename="memo.txt",
        ),
        findings=[
            RedFlagCandidateFinding(
                id="red-informal-approval",
                red_flag_type=RedFlagType.INFORMAL_APPROVAL,
                title="Informal approval channel is documented",
                description="Approval was documented through WhatsApp.",
                severity=RedFlagSeverity.MEDIUM,
                evidence=[
                    RedFlagEvidence(
                        text="Approval was informal via WhatsApp after payment."
                    )
                ],
            )
        ],
    )


def _accounting_output() -> AccountingAuditAgentOutput:
    return AccountingAuditAgentOutput(
        metadata=AgentOutputMetadata(
            agent_role=AgentRole.ACCOUNTING_AUDIT,
            document_id="document-1",
            source_filename="memo.txt",
        ),
        findings=[
            AccountingAuditCandidateFinding(
                id="audit-approval-weakness",
                category=AccountingAuditCategory.APPROVAL_WEAKNESS,
                title="Approval weakness is documented",
                description="Approval is informal and late.",
                severity=AccountingAuditSeverity.HIGH,
                evidence=[
                    AccountingAuditEvidence(
                        text="Approval was informal via WhatsApp after payment."
                    )
                ],
            )
        ],
    )

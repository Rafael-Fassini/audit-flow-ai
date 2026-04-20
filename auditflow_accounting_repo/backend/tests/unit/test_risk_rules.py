from app.models.accounting_process import (
    AccountReference,
    AccountReferenceRole,
    AccountingProcess,
    EvidenceSnippet,
    ProcessStep,
    ProcessStepType,
)
from app.models.risk import InconsistencyType, RiskCategory
from app.services.risk_engine.rules import AccountingRiskRules


def test_rules_flag_generic_account_usage_and_missing_control() -> None:
    process = AccountingProcess(
        process_name="Suspense posting",
        summary="The accounting team records a suspense account entry.",
        source_filename="walkthrough.txt",
        steps=[
            ProcessStep(
                index=0,
                step_type=ProcessStepType.POSTING,
                description="The accounting team posts the suspense account entry.",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="posts the suspense account entry",
                ),
            )
        ],
        account_references=[
            AccountReference(
                role=AccountReferenceRole.DEBIT,
                account_code="9999",
                account_name="suspense account",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="debit 9999 suspense account",
                ),
            )
        ],
        posting_logic=["The accounting team posts the suspense account entry."],
    )

    result = AccountingRiskRules().evaluate(process)

    assert any(
        finding.type == InconsistencyType.ACCOUNT_USAGE
        for finding in result.inconsistencies
    )
    assert any(
        finding.id == "heuristic-unbalanced-posting-roles"
        for finding in result.inconsistencies
    )
    assert any(risk.category == RiskCategory.GENERIC_ACCOUNT_OVERUSE for risk in result.risks)
    assert all(risk.related_inconsistency_ids for risk in result.risks)


def test_rules_do_not_flag_missing_support_when_rationale_is_present() -> None:
    process = AccountingProcess(
        process_name="Accrual posting",
        summary="The accounting team records an accrual with invoice evidence.",
        source_filename="walkthrough.txt",
        steps=[
            ProcessStep(
                index=0,
                step_type=ProcessStepType.POSTING,
                description="The controller reviews invoice evidence before posting.",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="reviews invoice evidence before posting",
                ),
            )
        ],
        posting_logic=["The entry debits expense and credits accrued liabilities."],
    )

    result = AccountingRiskRules().evaluate(process)

    assert all(finding.id != "heuristic-missing-support" for finding in result.inconsistencies)
    assert all(finding.id != "heuristic-missing-control" for finding in result.inconsistencies)

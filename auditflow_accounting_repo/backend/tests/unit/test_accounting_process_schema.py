import pytest
from pydantic import ValidationError

from app.models.accounting_process import (
    AccountingProcess,
    EvidenceSnippet,
    ProcessStep,
    ProcessStepType,
)


def test_accounting_process_validates_sequential_step_indexes() -> None:
    evidence = EvidenceSnippet(section_index=0, chunk_index=0, text="Approved entry.")

    with pytest.raises(ValidationError):
        AccountingProcess(
            process_name="Month-end close",
            summary="The accounting team records accrual entries.",
            source_filename="memo.txt",
            steps=[
                ProcessStep(
                    index=1,
                    step_type=ProcessStepType.POSTING,
                    description="The accounting team posts the entry.",
                    evidence=evidence,
                )
            ],
        )


def test_accounting_process_accepts_minimal_valid_structure() -> None:
    process = AccountingProcess(
        process_name="Revenue recognition",
        summary="The accounting team records revenue entries.",
        source_filename="walkthrough.txt",
    )

    assert process.process_name == "Revenue recognition"
    assert process.steps == []
    assert process.account_references == []

from pathlib import Path

from app.models.accounting_process import AccountReferenceRole, ProcessStepType
from app.models.document_section import DocumentFormat, ParsedDocument
from app.repositories.accounting_process_repository import JsonAccountingProcessRepository
from app.services.chunking.document_chunker import DocumentChunker
from app.services.extraction.accounting_process_extractor import (
    AccountingProcessExtractor,
)


def test_extractor_structures_accounting_entry_process() -> None:
    chunked = DocumentChunker(max_chunk_chars=500).chunk(
        ParsedDocument(
            filename="walkthrough.txt",
            document_format=DocumentFormat.TXT,
            text=(
                "MONTH-END ACCRUAL PROCESS\n\n"
                "The accounting team receives the vendor estimate in SAP. "
                "The manager approves the support before posting. "
                "The accounting team posts the journal entry and debit 6100 expense "
                "and credit 2100 accrued liabilities. "
                "The chart of accounts requires expense classification by business event. "
                "The reviewer performs a control review after posting. "
                "The rationale is unclear and missing supporting evidence."
            ),
        )
    )

    process = AccountingProcessExtractor().extract(chunked)

    assert process.process_name == "MONTH-END ACCRUAL PROCESS"
    assert process.source_filename == "walkthrough.txt"
    assert process.steps
    assert any(step.step_type == ProcessStepType.POSTING for step in process.steps)
    assert any("Accounting Team" in step.actors for step in process.steps)
    assert any("SAP" in step.systems for step in process.steps)
    assert any(
        account.role == AccountReferenceRole.DEBIT
        and account.account_code == "6100"
        and account.account_name.lower() == "expense"
        for account in process.account_references
    )
    assert any(
        account.role == AccountReferenceRole.CREDIT
        and account.account_code == "2100"
        and account.account_name.lower() == "accrued liabilities"
        for account in process.account_references
    )
    assert process.chart_of_accounts_references
    assert process.controls
    assert process.posting_logic
    assert process.narrative_gaps


def test_accounting_process_repository_persists_process_contract(tmp_path: Path) -> None:
    chunked = DocumentChunker(max_chunk_chars=500).chunk(
        ParsedDocument(
            filename="policy.txt",
            document_format=DocumentFormat.TXT,
            text=(
                "POSTING POLICY\n\n"
                "The controller reviews journal entries before posting. "
                "The accounting team credits revenue and debits cash."
            ),
        )
    )
    process = AccountingProcessExtractor().extract(chunked)
    repository = JsonAccountingProcessRepository(tmp_path / "processes.json")

    repository.save("process-1", process)
    persisted = repository.get("process-1")

    assert persisted is not None
    assert persisted.process_name == "POSTING POLICY"
    assert persisted.source_filename == "policy.txt"
    assert persisted.account_references

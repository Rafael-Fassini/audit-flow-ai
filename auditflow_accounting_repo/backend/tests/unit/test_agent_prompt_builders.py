from datetime import datetime, timezone
from pathlib import Path

from app.agents.prompts.accounting_audit import build_accounting_audit_prompt
from app.agents.prompts.document_understanding import (
    build_document_understanding_prompt,
)
from app.agents.prompts.process_structuring import build_process_structuring_prompt
from app.agents.prompts.red_flag import build_red_flag_prompt
from app.agents.prompts.report_assembly import build_report_assembly_prompt
from app.agents.prompts.risk_inference import build_risk_inference_prompt
from app.models.accounting_process import AccountingProcess
from app.models.document import DocumentMetadata, DocumentStatus
from app.models.document_section import (
    ChunkedDocument,
    DocumentChunk,
    DocumentFormat,
    DocumentSection,
)
from app.models.risk import RiskInferenceResult


def test_prompt_builders_return_schema_bound_payloads_without_model_config() -> None:
    document = ChunkedDocument(
        filename="memo.txt",
        document_format=DocumentFormat.TXT,
        text="The accounting team posts the entry.",
        sections=[
            DocumentSection(
                index=0,
                text="The accounting team posts the entry.",
                start_char=0,
                end_char=37,
            )
        ],
        chunks=[
            DocumentChunk(
                index=0,
                section_index=0,
                text="The accounting team posts the entry.",
                start_char=0,
                end_char=37,
            )
        ],
    )
    process = AccountingProcess(
        process_name="Entry posting",
        summary="The accounting team posts the entry.",
        source_filename="memo.txt",
    )

    payloads = [
        build_document_understanding_prompt(
            document,
            DocumentMetadata(
                id="document-1",
                original_filename="memo.txt",
                content_type="text/plain",
                size_bytes=128,
                storage_path=Path("storage/uploads/memo.txt"),
                status=DocumentStatus.STORED,
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
        ),
        build_red_flag_prompt(
            document,
            DocumentMetadata(
                id="document-1",
                original_filename="memo.txt",
                content_type="text/plain",
                size_bytes=128,
                storage_path=Path("storage/uploads/memo.txt"),
                status=DocumentStatus.STORED,
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
        ),
        build_accounting_audit_prompt(
            document,
            DocumentMetadata(
                id="document-1",
                original_filename="memo.txt",
                content_type="text/plain",
                size_bytes=128,
                storage_path=Path("storage/uploads/memo.txt"),
                status=DocumentStatus.STORED,
                created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            ),
        ),
        build_process_structuring_prompt(document),
        build_risk_inference_prompt(process, []),
        build_report_assembly_prompt(process, RiskInferenceResult()),
    ]

    assert [payload.response_schema for payload in payloads] == [
        "DocumentUnderstandingAgentOutput",
        "RedFlagAgentOutput",
        "AccountingAuditAgentOutput",
        "ProcessStructurerAgentOutput",
        "RiskInferenceAgentOutput",
        "ReportAssemblerAgentOutput",
    ]
    assert all(payload.messages for payload in payloads)
    assert all("model" not in payload.model_dump() for payload in payloads)

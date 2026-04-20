from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agents.orchestrator import MultiAgentAnalysisOrchestrator
from app.agents.accounting_audit import AccountingAuditAgent
from app.agents.document_understanding import DocumentUnderstandingAgent
from app.agents.red_flag import RedFlagAgent
from app.agents.report import ReportAgent
from app.agents.reviewer import ReviewerAgent
from app.models.accounting_process import AccountingProcess
from app.models.document import DocumentMetadata, DocumentStatus
from app.models.document_section import DocumentFormat, ParsedDocument
from app.models.report import AnalysisReport, AnalysisStatus, AnalysisSummary
from app.schemas.agents import AgentRole


class ExplodingUnderstandingAgent:
    def understand(self, *args, **kwargs):
        raise RuntimeError("secret-token-should-not-leak")


class UnusedAgent:
    pass


def test_multi_agent_orchestrator_returns_safe_envelope_on_failure() -> None:
    base_report = _base_report()
    orchestrator = MultiAgentAnalysisOrchestrator(
        document_understanding_agent=ExplodingUnderstandingAgent(),
        red_flag_agent=UnusedAgent(),
        accounting_audit_agent=UnusedAgent(),
        reviewer_agent=ReviewerAgent(),
        report_agent=ReportAgent(),
    )

    output = orchestrator.enrich_report(
        base_report=base_report,
        parsed_document=ParsedDocument(
            filename="memo.txt",
            document_format=DocumentFormat.TXT,
            text="Clean memo text.",
        ),
        document_metadata=_metadata(),
    )

    assert output == base_report
    assert len(orchestrator.last_error_envelopes) == 1
    envelope = orchestrator.last_error_envelopes[0]
    assert envelope.stage == AgentRole.REVIEWER
    assert envelope.code == "multi_agent_enrichment_failed"
    assert "secret-token-should-not-leak" not in envelope.model_dump_json()


def test_agent_modules_do_not_hardcode_runtime_model_config() -> None:
    agents_root = Path(__file__).resolve().parents[2] / "app" / "agents"
    forbidden_tokens = (
        "gpt-",
        "OPENAI_API_KEY",
        "AGENT_MODEL",
        "agent_model=",
        "openai_model=",
    )

    violations: list[str] = []
    for path in agents_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            if token in text:
                violations.append(f"{path.name}:{token}")

    assert violations == []


def test_malformed_agent_provider_outputs_use_controlled_failure_modes() -> None:
    class MalformedProvider:
        def generate(self, prompt):
            return "{not valid json"

    parsed_document = ParsedDocument(
        filename="memo.txt",
        document_format=DocumentFormat.TXT,
        text=(
            "The invoice, contract, and payment support were attached. "
            "Formal approval was documented before posting."
        ),
    )
    metadata = _metadata()

    understanding = DocumentUnderstandingAgent(
        model_provider=MalformedProvider()
    ).understand(parsed_document, metadata)
    red_flags = RedFlagAgent(model_provider=MalformedProvider()).detect(
        parsed_document,
        metadata,
    )
    audit = AccountingAuditAgent(model_provider=MalformedProvider()).classify(
        parsed_document,
        metadata,
    )

    assert understanding.metadata.status.value == "needs_review"
    assert understanding.metadata.errors[0].code == "invalid_model_output"
    assert red_flags.metadata.status.value == "needs_review"
    assert red_flags.metadata.errors[0].code == "invalid_red_flag_model_output"
    assert audit.metadata.status.value == "needs_review"
    assert audit.metadata.errors[0].code == "invalid_accounting_audit_model_output"
    assert "{not valid json" not in understanding.model_dump_json()
    assert "{not valid json" not in red_flags.model_dump_json()
    assert "{not valid json" not in audit.model_dump_json()


def test_safe_error_envelope_rejects_blank_public_fields() -> None:
    from app.schemas.agents import SafeAgentErrorEnvelope

    with pytest.raises(ValueError):
        SafeAgentErrorEnvelope(
            stage=AgentRole.REVIEWER,
            code="",
            message="safe message",
        )


def _metadata() -> DocumentMetadata:
    return DocumentMetadata(
        id="document-1",
        original_filename="memo.txt",
        content_type="text/plain",
        size_bytes=128,
        storage_path=Path("storage/uploads/memo.txt"),
        status=DocumentStatus.STORED,
        created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )


def _base_report() -> AnalysisReport:
    return AnalysisReport(
        analysis_id="analysis-1",
        status=AnalysisStatus.COMPLETED,
        generated_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        summary=AnalysisSummary(
            process_name="Memo",
            source_filename="memo.txt",
            total_findings=0,
            high_severity_findings=0,
            review_required_count=0,
        ),
        process=AccountingProcess(
            process_name="Memo",
            summary="Clean memo.",
            source_filename="memo.txt",
        ),
    )

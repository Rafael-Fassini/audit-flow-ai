import pytest
from pydantic import ValidationError

from app.models.accounting_process import AccountingProcess
from app.models.document_section import (
    ChunkedDocument,
    DocumentChunk,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
)
from app.models.risk import RiskInferenceResult
from app.schemas.analysis import (
    ANALYSIS_CONTRACT_VERSION,
    ANALYSIS_MIGRATION_POINTS,
    AnalysisContractMetadata,
    AnalysisStage,
    DocumentChunkingRequest,
    DocumentParsingRequest,
    KnowledgeRetrievalRequest,
    ProcessStructuringRequest,
    ReportAssemblyRequest,
    RiskInferenceRequest,
)


def test_analysis_contract_metadata_freezes_version() -> None:
    metadata = AnalysisContractMetadata(
        analysis_id="analysis-1",
        document_id="document-1",
        source_filename="memo.txt",
    )

    assert metadata.contract_version == ANALYSIS_CONTRACT_VERSION

    with pytest.raises(ValidationError):
        AnalysisContractMetadata(contract_version="analysis.v2")


def test_stage_contracts_accept_existing_pipeline_models() -> None:
    metadata = AnalysisContractMetadata(document_id="document-1")
    parsed_document = ParsedDocument(
        filename="memo.txt",
        document_format=DocumentFormat.TXT,
        text="The accounting team posts the entry.",
    )
    chunked_document = ChunkedDocument(
        filename=parsed_document.filename,
        document_format=parsed_document.document_format,
        text=parsed_document.text,
        sections=[
            DocumentSection(
                index=0,
                text=parsed_document.text,
                start_char=0,
                end_char=len(parsed_document.text),
            )
        ],
        chunks=[
            DocumentChunk(
                index=0,
                section_index=0,
                text=parsed_document.text,
                start_char=0,
                end_char=len(parsed_document.text),
            )
        ],
    )
    process = AccountingProcess(
        process_name="Entry posting",
        summary="The accounting team posts the entry.",
        source_filename="memo.txt",
    )
    risk_result = RiskInferenceResult()

    assert DocumentParsingRequest(
        metadata=metadata,
        filename="memo.txt",
        content=b"The accounting team posts the entry.",
    )
    assert DocumentChunkingRequest(
        metadata=metadata,
        parsed_document=parsed_document,
    )
    assert ProcessStructuringRequest(
        metadata=metadata,
        chunked_document=chunked_document,
    )
    assert KnowledgeRetrievalRequest(metadata=metadata, process=process)
    assert RiskInferenceRequest(
        metadata=metadata,
        process=process,
        retrieved_context=[],
    )
    assert ReportAssemblyRequest(
        metadata=metadata,
        process=process,
        risk_result=risk_result,
    )


def test_knowledge_retrieval_contract_validates_limit() -> None:
    process = AccountingProcess(
        process_name="Entry posting",
        summary="The accounting team posts the entry.",
        source_filename="memo.txt",
    )

    with pytest.raises(ValidationError):
        KnowledgeRetrievalRequest(
            metadata=AnalysisContractMetadata(),
            process=process,
            limit=0,
        )


def test_migration_points_cover_current_analysis_flow_and_risks() -> None:
    stages = {point.stage for point in ANALYSIS_MIGRATION_POINTS}
    risks = [
        risk
        for point in ANALYSIS_MIGRATION_POINTS
        for risk in point.hardcoded_config_risks
    ]
    services = {
        service
        for point in ANALYSIS_MIGRATION_POINTS
        for service in point.reusable_services
    }

    assert stages == set(AnalysisStage)
    assert "DocumentParser" in services
    assert "KnowledgeRetrievalService" in services
    assert any("DeterministicEmbeddingProvider" in risk for risk in risks)
    assert any("NoOpLLMRiskInferenceProvider" in risk for risk in risks)

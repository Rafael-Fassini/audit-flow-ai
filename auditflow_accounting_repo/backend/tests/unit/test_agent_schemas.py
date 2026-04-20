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
from app.schemas.agents import (
    AGENT_OUTPUT_CONTRACT_VERSION,
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    DocumentChunkerAgentOutput,
    DocumentLoaderAgentOutput,
    DocumentParserAgentOutput,
    ProcessStructurerAgentOutput,
    RiskInferenceAgentOutput,
)


def test_agent_output_metadata_freezes_contract_version() -> None:
    metadata = AgentOutputMetadata(agent_role=AgentRole.PROCESS_STRUCTURER)

    assert metadata.contract_version == AGENT_OUTPUT_CONTRACT_VERSION

    with pytest.raises(ValidationError):
        AgentOutputMetadata(
            contract_version="agent-output.v2",
            agent_role=AgentRole.PROCESS_STRUCTURER,
        )


def test_failed_agent_output_requires_safe_error_details() -> None:
    with pytest.raises(ValidationError):
        AgentOutputMetadata(
            agent_role=AgentRole.RISK_INFERENCE,
            status=AgentOutputStatus.FAILED,
        )

    metadata = AgentOutputMetadata(
        agent_role=AgentRole.RISK_INFERENCE,
        status=AgentOutputStatus.FAILED,
        errors=[
            AgentError(
                code="invalid_model_response",
                message="Model output did not validate.",
                retryable=True,
            )
        ],
    )

    assert metadata.status == AgentOutputStatus.FAILED
    assert metadata.errors[0].retryable is True


def test_agent_output_schemas_accept_current_pipeline_models() -> None:
    metadata = AgentOutputMetadata(
        agent_role=AgentRole.DOCUMENT_PARSER,
        analysis_id="analysis-1",
        document_id="document-1",
        source_filename="memo.txt",
    )
    parsed_document = _parsed_document()
    chunked_document = _chunked_document(parsed_document)
    process = AccountingProcess(
        process_name="Entry posting",
        summary="The accounting team posts the entry.",
        source_filename="memo.txt",
    )

    assert DocumentLoaderAgentOutput(
        metadata=metadata.model_copy(update={"agent_role": AgentRole.DOCUMENT_LOADER}),
        filename="memo.txt",
        size_bytes=128,
        content_sha256="a" * 64,
    )
    assert DocumentParserAgentOutput(
        metadata=metadata,
        parsed_document=parsed_document,
    )
    assert DocumentChunkerAgentOutput(
        metadata=metadata.model_copy(update={"agent_role": AgentRole.DOCUMENT_CHUNKER}),
        chunked_document=chunked_document,
    )
    assert ProcessStructurerAgentOutput(
        metadata=metadata.model_copy(
            update={"agent_role": AgentRole.PROCESS_STRUCTURER}
        ),
        process=process,
    )
    assert RiskInferenceAgentOutput(
        metadata=metadata.model_copy(update={"agent_role": AgentRole.RISK_INFERENCE}),
        risk_result=RiskInferenceResult(),
    )


def test_document_loader_output_rejects_invalid_digest() -> None:
    with pytest.raises(ValidationError):
        DocumentLoaderAgentOutput(
            metadata=AgentOutputMetadata(agent_role=AgentRole.DOCUMENT_LOADER),
            filename="memo.txt",
            size_bytes=128,
            content_sha256="not-a-sha256",
        )


def _parsed_document() -> ParsedDocument:
    return ParsedDocument(
        filename="memo.txt",
        document_format=DocumentFormat.TXT,
        text="The accounting team posts the entry.",
    )


def _chunked_document(parsed_document: ParsedDocument) -> ChunkedDocument:
    return ChunkedDocument(
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

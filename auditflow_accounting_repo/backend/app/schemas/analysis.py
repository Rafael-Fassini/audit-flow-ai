from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.accounting_process import AccountingProcess
from app.models.document_section import ChunkedDocument, ParsedDocument
from app.models.knowledge_base import RetrievalResult
from app.models.report import AnalysisReport
from app.models.risk import RiskInferenceResult


ANALYSIS_CONTRACT_VERSION = "analysis.v1"


class AnalysisAssemblyRequest(BaseModel):
    process: AccountingProcess
    risk_result: RiskInferenceResult
    analysis_id: str | None = None


class AnalysisStage(str, Enum):
    DOCUMENT_LOADING = "document_loading"
    PARSING = "parsing"
    CHUNKING = "chunking"
    PROCESS_STRUCTURING = "process_structuring"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    RISK_INFERENCE = "risk_inference"
    REPORT_ASSEMBLY = "report_assembly"


class AnalysisAgentRole(str, Enum):
    DOCUMENT_LOADER = "document_loader"
    DOCUMENT_PARSER = "document_parser"
    DOCUMENT_CHUNKER = "document_chunker"
    PROCESS_STRUCTURER = "process_structurer"
    KNOWLEDGE_RETRIEVER = "knowledge_retriever"
    RISK_INFERENCE = "risk_inference"
    REPORT_ASSEMBLER = "report_assembler"


class AnalysisContractMetadata(BaseModel):
    contract_version: Literal["analysis.v1"] = ANALYSIS_CONTRACT_VERSION
    analysis_id: str | None = None
    document_id: str | None = None
    source_filename: str | None = None


class DocumentLoadingResult(BaseModel):
    metadata: AnalysisContractMetadata
    filename: str = Field(min_length=1)
    content: bytes


class DocumentParsingRequest(BaseModel):
    metadata: AnalysisContractMetadata
    filename: str = Field(min_length=1)
    content: bytes


class DocumentParsingResult(BaseModel):
    metadata: AnalysisContractMetadata
    parsed_document: ParsedDocument


class DocumentChunkingRequest(BaseModel):
    metadata: AnalysisContractMetadata
    parsed_document: ParsedDocument


class DocumentChunkingResult(BaseModel):
    metadata: AnalysisContractMetadata
    chunked_document: ChunkedDocument


class ProcessStructuringRequest(BaseModel):
    metadata: AnalysisContractMetadata
    chunked_document: ChunkedDocument


class ProcessStructuringResult(BaseModel):
    metadata: AnalysisContractMetadata
    process: AccountingProcess


class KnowledgeRetrievalRequest(BaseModel):
    metadata: AnalysisContractMetadata
    process: AccountingProcess
    limit: int | None = Field(default=None, ge=1)
    metadata_filter: dict[str, str] | None = None
    preferred_document_scope: str | None = None
    preferred_regime_applicability: str | None = None


class KnowledgeRetrievalContractResult(BaseModel):
    metadata: AnalysisContractMetadata
    retrieved_context: list[RetrievalResult] = Field(default_factory=list)


class RiskInferenceRequest(BaseModel):
    metadata: AnalysisContractMetadata
    process: AccountingProcess
    retrieved_context: list[RetrievalResult] = Field(default_factory=list)


class RiskInferenceContractResult(BaseModel):
    metadata: AnalysisContractMetadata
    risk_result: RiskInferenceResult


class ReportAssemblyRequest(BaseModel):
    metadata: AnalysisContractMetadata
    process: AccountingProcess
    risk_result: RiskInferenceResult
    analysis_id: str | None = None


class ReportAssemblyResult(BaseModel):
    metadata: AnalysisContractMetadata
    report: AnalysisReport


class AnalysisMigrationPoint(BaseModel):
    stage: AnalysisStage
    current_owner: str = Field(min_length=1)
    target_agent_role: AnalysisAgentRole
    reusable_services: list[str] = Field(default_factory=list)
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)
    hardcoded_config_risks: list[str] = Field(default_factory=list)
    migration_notes: str = Field(min_length=1)


ANALYSIS_MIGRATION_POINTS: tuple[AnalysisMigrationPoint, ...] = (
    AnalysisMigrationPoint(
        stage=AnalysisStage.DOCUMENT_LOADING,
        current_owner="DocumentAnalysisOrchestrator.analyze_document",
        target_agent_role=AnalysisAgentRole.DOCUMENT_LOADER,
        reusable_services=["JsonDocumentRepository"],
        contract_inputs=["document_id"],
        contract_outputs=["DocumentLoadingResult"],
        migration_notes=(
            "Keep repository lookup and stored-file validation as the first boundary "
            "before parsing work is delegated."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.PARSING,
        current_owner="DocumentAnalysisOrchestrator.analyze_document",
        target_agent_role=AnalysisAgentRole.DOCUMENT_PARSER,
        reusable_services=["DocumentParser"],
        contract_inputs=["DocumentParsingRequest"],
        contract_outputs=["DocumentParsingResult"],
        migration_notes=(
            "DocumentParser is reusable as-is for PDF, DOCX, and TXT extraction; "
            "unsupported or empty input errors should remain mapped to 422."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.CHUNKING,
        current_owner="DocumentAnalysisOrchestrator.analyze_document",
        target_agent_role=AnalysisAgentRole.DOCUMENT_CHUNKER,
        reusable_services=["DocumentChunker"],
        contract_inputs=["DocumentChunkingRequest"],
        contract_outputs=["DocumentChunkingResult"],
        hardcoded_config_risks=[
            "DocumentChunker() currently uses its constructor default max_chunk_chars=1200."
        ],
        migration_notes=(
            "Expose chunk-size policy through settings before changing behavior or "
            "moving this stage behind an agent boundary."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.PROCESS_STRUCTURING,
        current_owner="DocumentAnalysisOrchestrator.analyze_document",
        target_agent_role=AnalysisAgentRole.PROCESS_STRUCTURER,
        reusable_services=["AccountingProcessExtractor"],
        contract_inputs=["ProcessStructuringRequest"],
        contract_outputs=["ProcessStructuringResult"],
        hardcoded_config_risks=[
            "Extractor keyword dictionaries and language heuristics are module constants."
        ],
        migration_notes=(
            "Preserve AccountingProcess as the stable downstream schema while replacing "
            "or augmenting extraction internals."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.KNOWLEDGE_RETRIEVAL,
        current_owner="get_document_analysis_orchestrator",
        target_agent_role=AnalysisAgentRole.KNOWLEDGE_RETRIEVER,
        reusable_services=[
            "DeterministicEmbeddingProvider",
            "KnowledgeIndexer",
            "KnowledgeRetrievalService",
            "QdrantVectorStore",
            "default_knowledge_documents",
        ],
        contract_inputs=["KnowledgeRetrievalRequest"],
        contract_outputs=["KnowledgeRetrievalContractResult"],
        hardcoded_config_risks=[
            "Curated knowledge is indexed on dependency construction for every orchestrator build.",
            "DeterministicEmbeddingProvider is hardwired in the API dependency.",
            "QdrantVectorStore is constructed directly from settings.qdrant_url in the API layer.",
        ],
        migration_notes=(
            "Move index warm-up and embedding/vector-store selection behind a factory "
            "before retrieval is independently deployed or scheduled."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.RISK_INFERENCE,
        current_owner="get_document_analysis_orchestrator",
        target_agent_role=AnalysisAgentRole.RISK_INFERENCE,
        reusable_services=[
            "AccountingRiskRules",
            "HybridRiskInferenceService",
            "NoOpLLMRiskInferenceProvider",
        ],
        contract_inputs=["RiskInferenceRequest"],
        contract_outputs=["RiskInferenceContractResult"],
        hardcoded_config_risks=[
            "NoOpLLMRiskInferenceProvider is hardwired, so configured OpenAI settings are not used here."
        ],
        migration_notes=(
            "Keep RiskInferenceResult stable while swapping the LLM provider behind "
            "the existing hybrid service."
        ),
    ),
    AnalysisMigrationPoint(
        stage=AnalysisStage.REPORT_ASSEMBLY,
        current_owner="DocumentAnalysisOrchestrator.analyze_document",
        target_agent_role=AnalysisAgentRole.REPORT_ASSEMBLER,
        reusable_services=[
            "AnalysisReportBuilder",
            "FindingScorer",
            "JsonAnalysisReportRepository",
        ],
        contract_inputs=["ReportAssemblyRequest"],
        contract_outputs=["ReportAssemblyResult"],
        migration_notes=(
            "AnalysisReport remains the frozen response schema for the current "
            "analysis endpoints."
        ),
    ),
)

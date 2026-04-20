from fastapi import APIRouter, Depends, status
from fastapi import HTTPException
from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.models.report import AnalysisReport
from app.repositories.analysis_report_repository import JsonAnalysisReportRepository
from app.repositories.document_repository import JsonDocumentRepository
from app.schemas.analysis import AnalysisAssemblyRequest
from app.schemas.error import ErrorResponse
from app.services.analysis.document_analysis_orchestrator import (
    DocumentAnalysisInputError,
    DocumentAnalysisOrchestrator,
    DocumentNotFoundError,
    StoredDocumentFileNotFoundError,
)
from app.services.chunking.document_chunker import DocumentChunker
from app.services.extraction.accounting_process_extractor import (
    AccountingProcessExtractor,
)
from app.services.parsing.document_parser import DocumentParser
from app.services.reporting.analysis_report_builder import AnalysisReportBuilder
from app.services.scoring.finding_scorer import FindingScorer
from app.services.retrieval.curated_knowledge import default_knowledge_documents
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.vector_store import QdrantVectorStore
from app.services.risk_engine.hybrid_inference import HybridRiskInferenceService
from app.services.risk_engine.llm_inference import NoOpLLMRiskInferenceProvider
from app.services.risk_engine.rules import AccountingRiskRules

router = APIRouter(prefix="/analysis", tags=["analysis"])


async def get_analysis_report_builder() -> AnalysisReportBuilder:
    return AnalysisReportBuilder(scorer=FindingScorer())


async def get_document_analysis_orchestrator() -> DocumentAnalysisOrchestrator:
    settings = get_settings()
    embedding_provider = DeterministicEmbeddingProvider(
        vector_size=settings.embedding_vector_size
    )
    vector_store = QdrantVectorStore(QdrantClient(url=settings.qdrant_url))
    indexer = KnowledgeIndexer(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=settings.knowledge_collection_name,
    )
    indexer.index_documents(default_knowledge_documents())

    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=settings.knowledge_collection_name,
        default_limit=settings.retrieval_top_k,
    )

    return DocumentAnalysisOrchestrator(
        document_repository=JsonDocumentRepository(settings.document_metadata_path),
        parser=DocumentParser(),
        chunker=DocumentChunker(),
        extractor=AccountingProcessExtractor(),
        retrieval_service=retrieval_service,
        risk_inference_service=HybridRiskInferenceService(
            rules=AccountingRiskRules(),
            llm_provider=NoOpLLMRiskInferenceProvider(),
        ),
        report_builder=AnalysisReportBuilder(scorer=FindingScorer()),
        report_repository=JsonAnalysisReportRepository(settings.analysis_report_path),
    )


@router.post(
    "/reports",
    response_model=AnalysisReport,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def build_analysis_report(
    request: AnalysisAssemblyRequest,
    report_builder: AnalysisReportBuilder = Depends(get_analysis_report_builder),
) -> AnalysisReport:
    return report_builder.build(
        process=request.process,
        risk_result=request.risk_result,
        analysis_id=request.analysis_id,
    )


@router.post(
    "/documents/{document_id}",
    response_model=AnalysisReport,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def analyze_document(
    document_id: str,
    orchestrator: DocumentAnalysisOrchestrator = Depends(
        get_document_analysis_orchestrator
    ),
) -> AnalysisReport:
    try:
        return orchestrator.analyze_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StoredDocumentFileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentAnalysisInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

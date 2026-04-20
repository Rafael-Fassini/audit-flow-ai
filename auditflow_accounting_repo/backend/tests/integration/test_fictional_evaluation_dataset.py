import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.accounting_audit import AccountingAuditAgent
from app.agents.document_understanding import DocumentUnderstandingAgent
from app.agents.orchestrator import MultiAgentAnalysisOrchestrator
from app.agents.red_flag import RedFlagAgent
from app.agents.report import ReportAgent
from app.agents.reviewer import ReviewerAgent
from app.api.analysis import get_document_analysis_orchestrator
from app.api.documents import get_document_ingestion_service
from app.main import create_app
from app.repositories.analysis_report_repository import JsonAnalysisReportRepository
from app.repositories.document_repository import JsonDocumentRepository
from app.services.analysis.document_analysis_orchestrator import (
    DocumentAnalysisOrchestrator,
)
from app.services.chunking.document_chunker import DocumentChunker
from app.services.extraction.accounting_process_extractor import (
    AccountingProcessExtractor,
)
from app.services.ingestion.document_ingestion import DocumentIngestionService
from app.services.ingestion.storage import LocalInputFileStorage
from app.services.parsing.document_parser import DocumentParser
from app.services.reporting.analysis_report_builder import AnalysisReportBuilder
from app.services.retrieval.curated_knowledge import default_knowledge_documents
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.vector_store import InMemoryVectorStore
from app.services.risk_engine.hybrid_inference import HybridRiskInferenceService
from app.services.risk_engine.llm_inference import NoOpLLMRiskInferenceProvider
from app.services.risk_engine.rules import AccountingRiskRules
from app.services.scoring.finding_scorer import FindingScorer
from tests.fixtures.fictional_evaluation_dataset import (
    FICTIONAL_EVALUATION_DATASET,
    FictionalEvaluationCase,
)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case",
    FICTIONAL_EVALUATION_DATASET,
    ids=[case.case_id for case in FICTIONAL_EVALUATION_DATASET],
)
async def test_fictional_labeled_evaluation_dataset(case: FictionalEvaluationCase, tmp_path) -> None:
    app = _app_with_evaluation_services(tmp_path)

    payload = await _upload_and_analyze(
        app=app,
        filename=case.filename,
        text=case.document_text,
    )

    assert payload["final_response"]["conclusion"] == case.expected.conclusion

    categories = {finding["category"] for finding in payload["findings"]}
    assert case.expected.required_categories.issubset(categories)
    assert case.expected.forbidden_categories.isdisjoint(categories)

    evidence_text = " ".join(
        evidence["text"]
        for finding in payload["findings"]
        for evidence in finding["evidence"]
    )
    for term in case.expected.required_evidence_terms:
        assert term in evidence_text

    missing_items = " ".join(payload["final_response"]["missing_items"]).lower()
    for term in case.expected.required_missing_item_terms:
        assert term.lower() in missing_items

    assert len(payload["final_response"]["top_findings"]) <= 5
    if case.expected.conclusion == "NO":
        assert payload["final_response"]["top_findings"] == []
        assert payload["summary"]["total_findings"] == 0
    else:
        assert payload["final_response"]["top_findings"]


def _app_with_evaluation_services(tmp_path):
    metadata_path = tmp_path / "document_metadata.json"
    report_path = tmp_path / "analysis_reports.json"
    document_repository = JsonDocumentRepository(metadata_path)
    app = create_app()

    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=8192,
            ),
            repository=document_repository,
        )

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_evaluation_orchestrator(
            document_repository=document_repository,
            report_repository=JsonAnalysisReportRepository(report_path),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service
    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator
    return app


async def _upload_and_analyze(app, filename: str, text: str) -> dict:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload_response = await client.post(
            "/documents/",
            files={"file": (filename, text.encode("utf-8"), "text/plain")},
        )
        document_id = upload_response.json()["id"]
        analysis_response = await client.post(f"/analysis/documents/{document_id}")

    assert analysis_response.status_code == 201
    return analysis_response.json()


def _build_evaluation_orchestrator(
    document_repository: JsonDocumentRepository,
    report_repository: JsonAnalysisReportRepository,
) -> DocumentAnalysisOrchestrator:
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    vector_store = InMemoryVectorStore()
    collection_name = "knowledge"
    KnowledgeIndexer(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
    ).index_documents(default_knowledge_documents())

    return DocumentAnalysisOrchestrator(
        document_repository=document_repository,
        parser=DocumentParser(),
        chunker=DocumentChunker(),
        extractor=AccountingProcessExtractor(),
        retrieval_service=KnowledgeRetrievalService(
            vector_store=vector_store,
            embedding_provider=embedding_provider,
            collection_name=collection_name,
            default_limit=3,
        ),
        risk_inference_service=HybridRiskInferenceService(
            rules=AccountingRiskRules(),
            llm_provider=NoOpLLMRiskInferenceProvider(),
        ),
        report_builder=AnalysisReportBuilder(scorer=FindingScorer()),
        agent_orchestrator=MultiAgentAnalysisOrchestrator(
            document_understanding_agent=DocumentUnderstandingAgent(),
            red_flag_agent=RedFlagAgent(),
            accounting_audit_agent=AccountingAuditAgent(),
            reviewer_agent=ReviewerAgent(),
            report_agent=ReportAgent(),
        ),
        report_repository=report_repository,
    )

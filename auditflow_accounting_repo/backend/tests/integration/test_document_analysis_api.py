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


@pytest.mark.anyio
async def test_analyze_document_runs_pipeline_from_stored_document(tmp_path) -> None:
    metadata_path = tmp_path / "document_metadata.json"
    report_path = tmp_path / "analysis_reports.json"
    document_repository = JsonDocumentRepository(metadata_path)
    app = create_app()

    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=2048,
            ),
            repository=document_repository,
        )

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_test_orchestrator(
            document_repository=document_repository,
            report_repository=JsonAnalysisReportRepository(report_path),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service
    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload_response = await client.post(
            "/documents/",
            files={
                "file": (
                    "memorandum.txt",
                    (
                        b"The accounting team records a debit to suspense account. "
                        b"The manager approval is documented, but no closure deadline "
                        b"is documented."
                    ),
                    "text/plain",
                )
            },
        )
        document_id = upload_response.json()["id"]

        analysis_response = await client.post(
            f"/analysis/documents/{document_id}",
            headers={"X-Request-ID": "analysis-from-document-test"},
        )

    assert analysis_response.status_code == 201
    payload = analysis_response.json()
    assert payload["status"] == "completed"
    assert payload["summary"]["source_filename"] == "memorandum.txt"
    assert payload["summary"]["total_findings"] >= 1
    assert payload["process"]["account_references"]
    assert payload["findings"]
    assert payload["evidence"]
    assert JsonAnalysisReportRepository(report_path).get(payload["analysis_id"]) is not None


@pytest.mark.anyio
async def test_analyze_document_surfaces_operational_narrative_risks(tmp_path) -> None:
    metadata_path = tmp_path / "document_metadata.json"
    report_path = tmp_path / "analysis_reports.json"
    document_repository = JsonDocumentRepository(metadata_path)
    app = create_app()

    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=4096,
            ),
            repository=document_repository,
        )

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_test_orchestrator(
            document_repository=document_repository,
            report_repository=JsonAnalysisReportRepository(report_path),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service
    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator

    memorandum = (
        "Memorando Walkthrough Corretora\n\n"
        "Fluxo operacional\n\n"
        "1. A corretora recebe a solicitação operacional do cliente.\n"
        "2. O backoffice valida as informações recebidas de terceiros.\n"
        "3. A contabilidade registra o lançamento contábil no fechamento.\n\n"
        "Riscos Identificados\n\n"
        "Há limitação de rastreabilidade entre a solicitação original e o "
        "registro final. Existe dependência de terceiros para confirmar "
        "informações críticas.\n\n"
        "Controles Internos Observados\n\n"
        "O backoffice revisa as informações antes do fechamento.\n\n"
        "Limitações\n\n"
        "Não foi identificada referência ao plano de contas."
    ).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload_response = await client.post(
            "/documents/",
            files={"file": ("memorando_operacional.txt", memorandum, "text/plain")},
        )
        document_id = upload_response.json()["id"]

        analysis_response = await client.post(f"/analysis/documents/{document_id}")

    assert analysis_response.status_code == 201
    payload = analysis_response.json()
    assert 2 <= payload["summary"]["total_findings"] <= 4
    assert payload["process"]["process_name"] == "Processo operacional e contábil de corretora"
    assert len(payload["process"]["steps"]) >= 3
    assert all(len(step["description"].split()) >= 5 for step in payload["process"]["steps"])
    assert any(
        "Responsible party:" in step["description"]
        for step in payload["process"]["steps"]
    )
    assert payload["findings"]
    finding_titles = [finding["title"] for finding in payload["findings"]]
    assert len(finding_titles) == len(set(finding_titles))
    assert all(finding["description"].strip().lower() not in {"riscos", "riscos."} for finding in payload["findings"])
    categories = {finding["category"] for finding in payload["findings"]}
    assert "traceability_gap" in categories
    assert "third_party_dependency" in categories
    assert "documentary_gap" in categories
    assert "posting_logic" not in categories
    assert any(
        finding["category"] == "documentary_gap"
        and "accounting-entry details" in finding["title"]
        for finding in payload["findings"]
    )
    assert any(
        "traceability" in finding["title"].lower()
        or "rastreabilidade" in finding["description"].lower()
        for finding in payload["findings"]
    )
    assert payload["follow_up_questions"]
    assert any(
        "third" in question["question"].lower()
        or "terceiros" in question["question"].lower()
        or "rastreabilidade" in question["question"].lower()
        for question in payload["follow_up_questions"]
    )
    assert any(
        "Account references were not identified" in gap["description"]
        for gap in payload["process"]["narrative_gaps"]
    )
    assert any(
        "Chart-of-accounts references were not identified" in gap["description"]
        for gap in payload["process"]["narrative_gaps"]
    )
    knowledge_evidence = [
        evidence
        for finding in payload["findings"]
        for evidence in finding["evidence"]
        if evidence.get("source") == "knowledge_base"
    ]
    knowledge_ids = [evidence.get("knowledge_chunk_id") for evidence in knowledge_evidence]
    assert len(knowledge_ids) == len(set(knowledge_ids))


@pytest.mark.anyio
async def test_analyze_document_deduplicates_repeated_narrative_risks(tmp_path) -> None:
    metadata_path = tmp_path / "document_metadata.json"
    report_path = tmp_path / "analysis_reports.json"
    document_repository = JsonDocumentRepository(metadata_path)
    app = create_app()

    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=4096,
            ),
            repository=document_repository,
        )

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_test_orchestrator(
            document_repository=document_repository,
            report_repository=JsonAnalysisReportRepository(report_path),
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service
    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator

    memorandum = (
        "Memorando Walkthrough Corretora\n\n"
        "Riscos Identificados\n\n"
        "Riscos.\n"
        "Há limitação de rastreabilidade entre a solicitação original e o registro final.\n"
        "A rastreabilidade entre a solicitação original e o registro final é limitada.\n"
        "Existe dependência de terceiros para confirmar informações críticas.\n"
        "A confirmação de informações críticas depende de terceiros.\n\n"
        "Fluxo operacional\n\n"
        "A corretora recebe a solicitação operacional do cliente.\n"
        "O backoffice valida as informações recebidas de terceiros.\n"
        "A contabilidade registra o lançamento contábil no fechamento."
    ).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload_response = await client.post(
            "/documents/",
            files={"file": ("memorando_repetido.txt", memorandum, "text/plain")},
        )
        document_id = upload_response.json()["id"]

        analysis_response = await client.post(f"/analysis/documents/{document_id}")

    assert analysis_response.status_code == 201
    payload = analysis_response.json()
    titles = [finding["title"] for finding in payload["findings"]]
    assert titles.count("Narrative indicates traceability limitations") == 1
    assert titles.count("Narrative indicates third-party dependency") == 1
    categories = {finding["category"] for finding in payload["findings"]}
    assert "traceability_gap" in categories
    assert "third_party_dependency" in categories
    assert "posting_logic" not in categories
    assert all(finding["description"].strip().lower() != "riscos." for finding in payload["findings"])
    assert payload["follow_up_questions"]


@pytest.mark.anyio
async def test_analyze_document_returns_multi_agent_findings_for_known_memo(tmp_path) -> None:
    metadata_path = tmp_path / "document_metadata.json"
    report_path = tmp_path / "analysis_reports.json"
    document_repository = JsonDocumentRepository(metadata_path)
    app = create_app()

    async def get_test_ingestion_service() -> DocumentIngestionService:
        return DocumentIngestionService(
            storage=LocalInputFileStorage(
                storage_dir=tmp_path / "uploads",
                max_size_bytes=4096,
            ),
            repository=document_repository,
        )

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_test_orchestrator(
            document_repository=document_repository,
            report_repository=JsonAnalysisReportRepository(report_path),
            include_agents=True,
        )

    app.dependency_overrides[get_document_ingestion_service] = get_test_ingestion_service
    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator

    memorandum = (
        "Accounts Payable Red Flag Memo\n\n"
        "The accounting team receives the invoice on 2026-03-31. "
        "The accounting rationale is not documented and supporting evidence is missing. "
        "The review control was not performed before posting. "
        "The transaction cannot link to the source invoice, creating a traceability gap. "
        "The supplier balance is not reconciled at month end. "
        "Cost center CC-200 Sales does not match the IT services allocation. "
        "Approval was informal via WhatsApp after payment. "
        "Posting to account 4.1.01 - supplier expenses is inconsistent with the freight narrative. "
        "Invoice amount is R$ 1.000,00 but payment amount is R$ 1.500,00. "
        "No purchase order or contract was provided for the procurement."
    ).encode("utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        upload_response = await client.post(
            "/documents/",
            files={"file": ("ap_red_flag_memo.txt", memorandum, "text/plain")},
        )
        document_id = upload_response.json()["id"]

        analysis_response = await client.post(f"/analysis/documents/{document_id}")

    assert analysis_response.status_code == 201
    payload = analysis_response.json()
    assert payload["status"] == "completed"
    assert payload["summary"]["source_filename"] == "ap_red_flag_memo.txt"
    assert payload["summary"]["total_findings"] == len(payload["findings"])
    assert payload["summary"]["review_required_count"] >= 1
    agent_findings = [
        finding
        for finding in payload["findings"]
        if finding["source"] == "multi_agent"
    ]
    assert agent_findings
    categories = {finding["category"] for finding in agent_findings}
    assert "documentary_gap" in categories
    assert "control_gap" in categories
    assert "traceability_gap" in categories
    assert "reconciliation_gap" in categories
    assert "cost_center_inconsistency" in categories
    assert "approval_weakness" in categories
    assert "posting_inconsistency" in categories
    assert all(finding["evidence"] for finding in agent_findings)
    assert all(
        evidence["source"] == "document"
        for finding in agent_findings
        for evidence in finding["evidence"]
    )
    assert payload["follow_up_questions"]
    assert JsonAnalysisReportRepository(report_path).get(payload["analysis_id"]) is not None


@pytest.mark.anyio
async def test_analyze_document_returns_404_for_unknown_document(tmp_path) -> None:
    app = create_app()

    async def get_test_orchestrator() -> DocumentAnalysisOrchestrator:
        return _build_test_orchestrator(
            document_repository=JsonDocumentRepository(tmp_path / "missing.json"),
            report_repository=JsonAnalysisReportRepository(tmp_path / "reports.json"),
        )

    app.dependency_overrides[get_document_analysis_orchestrator] = get_test_orchestrator

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/analysis/documents/missing-document",
            headers={"X-Request-ID": "analysis-missing-document-test"},
        )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["request_id"] == "analysis-missing-document-test"


def _build_test_orchestrator(
    document_repository: JsonDocumentRepository,
    report_repository: JsonAnalysisReportRepository,
    include_agents: bool = False,
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
        agent_orchestrator=(
            MultiAgentAnalysisOrchestrator(
                document_understanding_agent=DocumentUnderstandingAgent(),
                red_flag_agent=RedFlagAgent(),
                accounting_audit_agent=AccountingAuditAgent(),
                reviewer_agent=ReviewerAgent(),
                report_agent=ReportAgent(),
            )
            if include_agents
            else None
        ),
        report_repository=report_repository,
    )

from datetime import datetime, timezone
from uuid import uuid4

from app.models.report import AnalysisReport
from app.agents.orchestrator import MultiAgentAnalysisOrchestrator
from app.models.accounting_process import AccountingProcess
from app.models.document_section import ParsedDocument
from app.models.report import AnalysisStatus, AnalysisSummary, FindingScore, ReportFinding
from app.models.risk import FindingEvidence, FollowUpQuestion
from app.repositories.analysis_report_repository import AnalysisReportRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking.document_chunker import DocumentChunker
from app.services.extraction.accounting_process_extractor import (
    AccountingProcessExtractor,
)
from app.services.parsing.document_parser import (
    DocumentParser,
    EmptyParsedTextError,
    UnsupportedDocumentFormatError,
)
from app.services.analysis.product_scope import ProductScopePolicy
from app.services.reporting.analysis_report_builder import AnalysisReportBuilder
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.risk_engine.hybrid_inference import HybridRiskInferenceService


class DocumentAnalysisError(Exception):
    pass


class DocumentNotFoundError(DocumentAnalysisError):
    pass


class StoredDocumentFileNotFoundError(DocumentAnalysisError):
    pass


class DocumentAnalysisInputError(DocumentAnalysisError):
    pass


class DocumentAnalysisOrchestrator:
    def __init__(
        self,
        document_repository: DocumentRepository,
        parser: DocumentParser,
        chunker: DocumentChunker,
        extractor: AccountingProcessExtractor,
        retrieval_service: KnowledgeRetrievalService,
        risk_inference_service: HybridRiskInferenceService,
        report_builder: AnalysisReportBuilder,
        agent_orchestrator: MultiAgentAnalysisOrchestrator | None = None,
        report_repository: AnalysisReportRepository | None = None,
        product_scope_policy: ProductScopePolicy | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._parser = parser
        self._chunker = chunker
        self._extractor = extractor
        self._retrieval_service = retrieval_service
        self._risk_inference_service = risk_inference_service
        self._report_builder = report_builder
        self._agent_orchestrator = agent_orchestrator
        self._report_repository = report_repository
        self._product_scope_policy = product_scope_policy or ProductScopePolicy()

    def analyze_document(self, document_id: str) -> AnalysisReport:
        document = self._document_repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' was not found.")
        if not document.storage_path.exists():
            raise StoredDocumentFileNotFoundError(
                f"Stored file for document '{document_id}' was not found."
            )

        content = document.storage_path.read_bytes()
        try:
            parsed_document = self._parser.parse(
                filename=document.original_filename,
                content=content,
            )
        except (UnsupportedDocumentFormatError, EmptyParsedTextError) as exc:
            raise DocumentAnalysisInputError(str(exc)) from exc

        chunked_document = self._chunker.chunk(parsed_document)
        process = self._extractor.extract(chunked_document)
        scope_assessment = self._product_scope_policy.assess(
            parsed_document=parsed_document,
            process=process,
        )
        if not scope_assessment.is_in_scope:
            report = self._build_out_of_scope_report(
                process=process,
                parsed_document=parsed_document,
                reason=scope_assessment.reason,
            )
            if self._report_repository is not None:
                self._report_repository.save(document_id=document.id, report=report)
            return report

        retrieved_context = self._retrieval_service.retrieve_for_process(
            process,
            allowed_document_families=(
                self._product_scope_policy.allowed_document_family_values()
            ),
        )
        risk_result = self._risk_inference_service.infer(
            process=process,
            retrieved_context=retrieved_context,
        )
        report = self._report_builder.build(
            process=process,
            risk_result=risk_result,
        )
        if self._agent_orchestrator is not None:
            try:
                report = self._agent_orchestrator.enrich_report(
                    base_report=report,
                    parsed_document=parsed_document,
                    document_metadata=document,
                )
            except Exception:
                report = report

        if self._report_repository is not None:
            self._report_repository.save(document_id=document.id, report=report)

        return report

    def _build_out_of_scope_report(
        self,
        process: AccountingProcess,
        parsed_document: ParsedDocument,
        reason: str,
    ) -> AnalysisReport:
        finding = ReportFinding(
            id="product-scope-out-of-scope",
            finding_type="scope",
            category="out_of_scope",
            title="Document is outside AuditFlow's approved product scope",
            description=reason,
            source="product_scope",
            score=FindingScore(
                severity="medium",
                confidence=0.95,
                review_required=True,
            ),
            evidence=[
                FindingEvidence(
                    source="document",
                    text=parsed_document.text[:280],
                    section_index=0,
                    chunk_index=0,
                )
            ],
        )
        return AnalysisReport(
            analysis_id=str(uuid4()),
            status=AnalysisStatus.COMPLETED,
            generated_at=datetime.now(timezone.utc),
            summary=AnalysisSummary(
                process_name=process.process_name,
                source_filename=process.source_filename,
                total_findings=1,
                high_severity_findings=0,
                review_required_count=1,
            ),
            process=process,
            findings=[finding],
            evidence=finding.evidence,
            follow_up_questions=[
                FollowUpQuestion(
                    id="question-product-scope",
                    question=(
                        "Can the request be provided as a memorandum, walkthrough, "
                        "payment support, or accounting-entry support document "
                        "within the approved AuditFlow scope?"
                    ),
                    rationale=(
                        "The current document cannot be assessed as a broad audit, "
                        "tax, legal, or unrestricted reform analysis."
                    ),
                    related_finding_ids=[finding.id],
                )
            ],
        )

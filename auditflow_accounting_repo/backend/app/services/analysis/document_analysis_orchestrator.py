from app.models.report import AnalysisReport
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
        report_repository: AnalysisReportRepository | None = None,
    ) -> None:
        self._document_repository = document_repository
        self._parser = parser
        self._chunker = chunker
        self._extractor = extractor
        self._retrieval_service = retrieval_service
        self._risk_inference_service = risk_inference_service
        self._report_builder = report_builder
        self._report_repository = report_repository

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
        retrieved_context = self._retrieval_service.retrieve_for_process(process)
        risk_result = self._risk_inference_service.infer(
            process=process,
            retrieved_context=retrieved_context,
        )
        report = self._report_builder.build(
            process=process,
            risk_result=risk_result,
        )

        if self._report_repository is not None:
            self._report_repository.save(document_id=document.id, report=report)

        return report

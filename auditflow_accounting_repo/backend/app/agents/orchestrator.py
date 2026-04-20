from app.agents.accounting_audit import AccountingAuditAgent
from app.agents.document_understanding import DocumentUnderstandingAgent
from app.agents.red_flag import RedFlagAgent
from app.agents.report import ReportAgent
from app.agents.reviewer import ReviewerAgent
from app.models.document import DocumentMetadata
from app.models.document_section import ParsedDocument
from app.models.report import AnalysisReport


class MultiAgentAnalysisOrchestrator:
    def __init__(
        self,
        document_understanding_agent: DocumentUnderstandingAgent,
        red_flag_agent: RedFlagAgent,
        accounting_audit_agent: AccountingAuditAgent,
        reviewer_agent: ReviewerAgent,
        report_agent: ReportAgent,
    ) -> None:
        self._document_understanding_agent = document_understanding_agent
        self._red_flag_agent = red_flag_agent
        self._accounting_audit_agent = accounting_audit_agent
        self._reviewer_agent = reviewer_agent
        self._report_agent = report_agent

    def enrich_report(
        self,
        base_report: AnalysisReport,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
    ) -> AnalysisReport:
        understanding_output = self._document_understanding_agent.understand(
            parsed_document=parsed_document,
            document_metadata=document_metadata,
            analysis_id=base_report.analysis_id,
        )
        red_flag_output = self._red_flag_agent.detect(
            parsed_document=parsed_document,
            document_metadata=document_metadata,
            understanding=understanding_output.understanding,
            analysis_id=base_report.analysis_id,
        )
        accounting_audit_output = self._accounting_audit_agent.classify(
            parsed_document=parsed_document,
            document_metadata=document_metadata,
            understanding=understanding_output.understanding,
            analysis_id=base_report.analysis_id,
        )
        reviewer_output = self._reviewer_agent.review(
            red_flag_output=red_flag_output,
            accounting_audit_output=accounting_audit_output,
            analysis_id=base_report.analysis_id,
        )
        return self._report_agent.build_final_report(
            base_report=base_report,
            reviewer_output=reviewer_output,
        )

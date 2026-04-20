from datetime import datetime, timezone
from uuid import uuid4

from app.models.accounting_process import AccountingProcess
from app.models.report import (
    AnalysisReport,
    AnalysisStatus,
    AnalysisSummary,
    FinalResponse,
    ReportFinding,
    ScopedQuestionAnswer,
)
from app.models.risk import FindingEvidence, RiskInferenceResult
from app.services.scoring.finding_scorer import FindingScorer


class AnalysisReportBuilder:
    def __init__(self, scorer: FindingScorer) -> None:
        self._scorer = scorer

    def build(
        self,
        process: AccountingProcess,
        risk_result: RiskInferenceResult,
        analysis_id: str | None = None,
    ) -> AnalysisReport:
        findings = self._build_findings(risk_result)
        evidence = self._dedupe_evidence(
            evidence
            for finding in findings
            for evidence in finding.evidence
        )
        summary = AnalysisSummary(
            process_name=process.process_name,
            source_filename=process.source_filename,
            total_findings=len(findings),
            high_severity_findings=sum(
                1 for finding in findings if finding.score.severity == "high"
            ),
            review_required_count=sum(
                1 for finding in findings if finding.score.review_required
            ),
        )

        scoped_answer = ScopedQuestionAnswer.from_findings(findings)

        return AnalysisReport(
            analysis_id=analysis_id or str(uuid4()),
            status=AnalysisStatus.COMPLETED,
            generated_at=datetime.now(timezone.utc),
            summary=summary,
            scoped_answer=scoped_answer,
            final_response=FinalResponse.from_analysis(
                scoped_answer=scoped_answer,
                findings=findings,
                follow_up_questions=risk_result.follow_up_questions,
            ),
            process=process,
            findings=findings,
            evidence=evidence,
            follow_up_questions=risk_result.follow_up_questions,
        )

    def _build_findings(
        self,
        risk_result: RiskInferenceResult,
    ) -> list[ReportFinding]:
        findings: list[ReportFinding] = []
        inconsistency_ids: set[str] = set()
        inconsistency_titles: set[str] = set()
        for inconsistency in risk_result.inconsistencies:
            inconsistency_ids.add(inconsistency.id)
            inconsistency_titles.add(inconsistency.title.lower())
            findings.append(
                ReportFinding(
                    id=inconsistency.id,
                    finding_type="inconsistency",
                    category=inconsistency.type.value,
                    title=inconsistency.title,
                    description=inconsistency.description,
                    source=inconsistency.source.value,
                    score=self._scorer.score_inconsistency(inconsistency),
                    evidence=inconsistency.evidence,
                )
            )

        for risk in risk_result.risks:
            if (
                risk.related_inconsistency_ids
                and any(
                    related_id in inconsistency_ids
                    for related_id in risk.related_inconsistency_ids
                )
                and risk.title.lower() in inconsistency_titles
            ):
                continue
            findings.append(
                ReportFinding(
                    id=risk.id,
                    finding_type="risk",
                    category=risk.category.value,
                    title=risk.title,
                    description=risk.description,
                    source=risk.source.value,
                    score=self._scorer.score_risk(risk),
                    related_finding_ids=risk.related_inconsistency_ids,
                    evidence=risk.evidence,
                )
            )

        return findings

    def _dedupe_evidence(
        self,
        evidence_items,
    ) -> list[FindingEvidence]:
        deduped: list[FindingEvidence] = []
        seen: set[tuple[object, ...]] = set()
        for evidence in evidence_items:
            key = (
                evidence.source,
                evidence.text,
                evidence.section_index,
                evidence.chunk_index,
                evidence.knowledge_chunk_id,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(evidence)
        return deduped

from app.models.report import AnalysisReport, AnalysisSummary, FindingScore, ReportFinding
from app.models.risk import FindingEvidence, FollowUpQuestion
from app.schemas.agents import (
    ReviewedFinding,
    ReviewerAgentOutput,
    ReviewerFollowUpQuestion,
)


class ReportAgent:
    def build_final_report(
        self,
        base_report: AnalysisReport,
        reviewer_output: ReviewerAgentOutput,
    ) -> AnalysisReport:
        reviewed_findings = (
            reviewer_output.operational_findings + reviewer_output.documentary_gaps
        )
        appended_findings = [
            self._report_finding(finding)
            for finding in reviewed_findings
            if finding.evidence
        ]
        findings = self._dedupe_findings(base_report.findings + appended_findings)
        evidence = self._dedupe_evidence(
            evidence
            for finding in findings
            for evidence in finding.evidence
        )
        follow_up_questions = self._dedupe_questions(
            base_report.follow_up_questions
            + [
                self._follow_up_question(question)
                for question in reviewer_output.follow_up_questions
            ]
        )

        return base_report.model_copy(
            deep=True,
            update={
                "summary": AnalysisSummary(
                    process_name=base_report.summary.process_name,
                    source_filename=base_report.summary.source_filename,
                    total_findings=len(findings),
                    high_severity_findings=sum(
                        1
                        for finding in findings
                        if finding.score.severity == "high"
                    ),
                    review_required_count=sum(
                        1
                        for finding in findings
                        if finding.score.review_required
                    ),
                ),
                "findings": findings,
                "evidence": evidence,
                "follow_up_questions": follow_up_questions,
            },
        )

    def _report_finding(self, finding: ReviewedFinding) -> ReportFinding:
        return ReportFinding(
            id=f"agent-{finding.id}",
            finding_type=finding.kind.value,
            category=finding.category,
            title=finding.title,
            description=finding.description,
            source="multi_agent",
            score=FindingScore(
                severity=finding.severity.value,
                confidence=finding.confidence,
                review_required=finding.review_required,
            ),
            related_finding_ids=finding.source_finding_ids,
            evidence=[
                FindingEvidence(
                    source=evidence.source,
                    text=evidence.text,
                )
                for evidence in finding.evidence
            ],
        )

    def _follow_up_question(
        self,
        question: ReviewerFollowUpQuestion,
    ) -> FollowUpQuestion:
        return FollowUpQuestion(
            id=f"agent-{question.id}",
            question=question.question,
            rationale=question.rationale,
            related_finding_ids=[
                f"agent-{finding_id}" for finding_id in question.related_finding_ids
            ],
        )

    def _dedupe_findings(
        self,
        findings: list[ReportFinding],
    ) -> list[ReportFinding]:
        deduped: list[ReportFinding] = []
        seen: set[tuple[str, str]] = set()
        for finding in findings:
            evidence_key = finding.evidence[0].text if finding.evidence else finding.title
            key = (finding.category, evidence_key.lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

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

    def _dedupe_questions(
        self,
        questions: list[FollowUpQuestion],
    ) -> list[FollowUpQuestion]:
        deduped: list[FollowUpQuestion] = []
        seen: set[str] = set()
        for question in questions:
            key = question.question.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(question)
        return deduped

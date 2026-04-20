import re

from app.schemas.agents import (
    AccountingAuditAgentOutput,
    AccountingAuditCategory,
    AccountingAuditSeverity,
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    RedFlagAgentOutput,
    RedFlagSeverity,
    RedFlagType,
    ReviewedFinding,
    ReviewerAgentOutput,
    ReviewerEvidence,
    ReviewerFindingKind,
    ReviewerFollowUpQuestion,
    ReviewerSeverity,
    ReviewerSource,
)


SEVERITY_RANK = {
    ReviewerSeverity.LOW: 1,
    ReviewerSeverity.MEDIUM: 2,
    ReviewerSeverity.HIGH: 3,
}


class ReviewerAgent:
    def review(
        self,
        red_flag_output: RedFlagAgentOutput | None = None,
        accounting_audit_output: AccountingAuditAgentOutput | None = None,
        analysis_id: str | None = None,
    ) -> ReviewerAgentOutput:
        source_errors = self._source_errors(red_flag_output, accounting_audit_output)
        source_needs_review = self._source_needs_review(
            red_flag_output,
            accounting_audit_output,
        )
        findings = self._dedupe_findings(
            self._findings_from_red_flags(red_flag_output)
            + self._findings_from_accounting_audit(accounting_audit_output)
        )
        operational_findings = [
            finding
            for finding in findings
            if finding.kind == ReviewerFindingKind.OPERATIONAL
        ]
        documentary_gaps = [
            finding
            for finding in findings
            if finding.kind == ReviewerFindingKind.DOCUMENTARY_GAP
        ]

        return ReviewerAgentOutput(
            metadata=AgentOutputMetadata(
                agent_role=AgentRole.REVIEWER,
                status=(
                    AgentOutputStatus.NEEDS_REVIEW
                    if source_errors or source_needs_review
                    else AgentOutputStatus.COMPLETED
                ),
                analysis_id=analysis_id,
                document_id=self._document_id(red_flag_output, accounting_audit_output),
                source_filename=self._source_filename(
                    red_flag_output,
                    accounting_audit_output,
                ),
                errors=source_errors,
            ),
            operational_findings=operational_findings,
            documentary_gaps=documentary_gaps,
            follow_up_questions=self._follow_up_questions(findings),
        )

    def _findings_from_red_flags(
        self,
        red_flag_output: RedFlagAgentOutput | None,
    ) -> list[ReviewedFinding]:
        if red_flag_output is None:
            return []
        reviewed: list[ReviewedFinding] = []
        for finding in red_flag_output.findings:
            severity = self._severity_from_red_flag(finding.severity)
            category = self._category_from_red_flag(finding.red_flag_type)
            reviewed.append(
                ReviewedFinding(
                    id=f"review-red-flag-{self._slug(finding.id)}",
                    kind=self._kind_from_category(category),
                    category=category,
                    title=finding.title,
                    description=finding.description,
                    severity=severity,
                    confidence=self._confidence(
                        severity=severity,
                        evidence_count=len(finding.evidence),
                        source_count=1,
                    ),
                    review_required=self._review_required(severity, 1),
                    source_finding_ids=[finding.id],
                    evidence=[
                        ReviewerEvidence(
                            text=evidence.text,
                            source=evidence.source,
                            source_agent=ReviewerSource.RED_FLAG,
                            source_finding_id=finding.id,
                        )
                        for evidence in finding.evidence
                    ],
                )
            )
        return reviewed

    def _findings_from_accounting_audit(
        self,
        accounting_audit_output: AccountingAuditAgentOutput | None,
    ) -> list[ReviewedFinding]:
        if accounting_audit_output is None:
            return []
        reviewed: list[ReviewedFinding] = []
        for finding in accounting_audit_output.findings:
            severity = self._severity_from_accounting_audit(finding.severity)
            kind = (
                ReviewerFindingKind.DOCUMENTARY_GAP
                if finding.category == AccountingAuditCategory.DOCUMENTARY_GAP
                else ReviewerFindingKind.OPERATIONAL
            )
            reviewed.append(
                ReviewedFinding(
                    id=f"review-accounting-audit-{self._slug(finding.id)}",
                    kind=kind,
                    category=finding.category.value,
                    title=finding.title,
                    description=finding.description,
                    severity=severity,
                    confidence=self._confidence(
                        severity=severity,
                        evidence_count=len(finding.evidence),
                        source_count=1,
                    ),
                    review_required=self._review_required(severity, 1),
                    source_finding_ids=[finding.id],
                    evidence=[
                        ReviewerEvidence(
                            text=evidence.text,
                            source=evidence.source,
                            source_agent=ReviewerSource.ACCOUNTING_AUDIT,
                            source_finding_id=finding.id,
                        )
                        for evidence in finding.evidence
                    ],
                )
            )
        return reviewed

    def _dedupe_findings(
        self,
        findings: list[ReviewedFinding],
    ) -> list[ReviewedFinding]:
        merged_by_key: dict[tuple[str, str], ReviewedFinding] = {}
        for finding in findings:
            key = self._semantic_key(finding)
            existing = merged_by_key.get(key)
            if existing is None:
                merged_by_key[key] = finding.model_copy(
                    deep=True,
                    update={
                        "evidence": list(finding.evidence),
                        "source_finding_ids": list(finding.source_finding_ids),
                    },
                )
                continue

            severity = self._max_severity(existing.severity, finding.severity)
            source_finding_ids = self._merge_unique(
                existing.source_finding_ids,
                finding.source_finding_ids,
            )
            evidence = self._merge_evidence(existing.evidence, finding.evidence)
            merged_by_key[key] = existing.model_copy(
                deep=True,
                update={
                    "severity": severity,
                    "confidence": self._confidence(
                        severity=severity,
                        evidence_count=len(evidence),
                        source_count=len(
                            {item.source_agent for item in evidence}
                        ),
                    ),
                    "review_required": self._review_required(
                        severity,
                        len({item.source_agent for item in evidence}),
                    ),
                    "source_finding_ids": source_finding_ids,
                    "evidence": evidence,
                },
            )
        return list(merged_by_key.values())

    def _merge_evidence(
        self,
        existing: list[ReviewerEvidence],
        incoming: list[ReviewerEvidence],
    ) -> list[ReviewerEvidence]:
        merged: list[ReviewerEvidence] = []
        seen: set[tuple[str, ReviewerSource, str]] = set()
        for evidence in existing + incoming:
            key = (
                evidence.text,
                evidence.source_agent,
                evidence.source_finding_id,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(evidence.model_copy(deep=True))
        return merged

    def _follow_up_questions(
        self,
        findings: list[ReviewedFinding],
    ) -> list[ReviewerFollowUpQuestion]:
        questions: list[ReviewerFollowUpQuestion] = []
        for finding in findings:
            if not finding.review_required:
                continue
            question = self._question_for_finding(finding)
            questions.append(
                ReviewerFollowUpQuestion(
                    id=f"follow-up-{self._slug(finding.id)}",
                    question=question,
                    rationale=(
                        "Reviewer confirmation is required because the finding has "
                        f"{finding.severity.value} severity or needs corroboration."
                    ),
                    related_finding_ids=[finding.id],
                )
            )
        return questions

    def _question_for_finding(self, finding: ReviewedFinding) -> str:
        if finding.kind == ReviewerFindingKind.DOCUMENTARY_GAP:
            return (
                "Which source documents or accounting support resolve this "
                f"documentary gap: {finding.title}?"
            )
        if "approval" in finding.category:
            return (
                "Which formal approval evidence supports or remediates this "
                f"approval issue: {finding.title}?"
            )
        if "reconciliation" in finding.category:
            return (
                "Which reconciliation workpaper resolves this issue: "
                f"{finding.title}?"
            )
        return f"What evidence supports remediation or acceptance of: {finding.title}?"

    def _source_errors(
        self,
        red_flag_output: RedFlagAgentOutput | None,
        accounting_audit_output: AccountingAuditAgentOutput | None,
    ) -> list[AgentError]:
        errors: list[AgentError] = []
        for output in (red_flag_output, accounting_audit_output):
            if output is None:
                continue
            if output.metadata.status in {
                AgentOutputStatus.NEEDS_REVIEW,
                AgentOutputStatus.FAILED,
            }:
                errors.extend(error.model_copy(deep=True) for error in output.metadata.errors)
        return errors

    def _source_needs_review(
        self,
        red_flag_output: RedFlagAgentOutput | None,
        accounting_audit_output: AccountingAuditAgentOutput | None,
    ) -> bool:
        return any(
            output is not None
            and output.metadata.status in {
                AgentOutputStatus.NEEDS_REVIEW,
                AgentOutputStatus.FAILED,
            }
            for output in (red_flag_output, accounting_audit_output)
        )

    def _category_from_red_flag(self, red_flag_type: RedFlagType) -> str:
        mapping = {
            RedFlagType.MISSING_PROCUREMENT_ARTIFACTS: "documentary_gap",
            RedFlagType.INFORMAL_APPROVAL: "approval_weakness",
            RedFlagType.INFORMAL_PAYMENT_INSTRUCTIONS: "approval_weakness",
            RedFlagType.PAYMENT_BEFORE_INVOICE: "posting_inconsistency",
            RedFlagType.CONFLICTING_VALUES: "posting_inconsistency",
            RedFlagType.IMPOSSIBLE_DATE: "documentary_gap",
            RedFlagType.PAYMENT_TO_PERSONAL_OR_THIRD_PARTY_ACCOUNT: (
                "payment_control_weakness"
            ),
            RedFlagType.URGENCY_OVERRIDE_WITHOUT_SUPPORT: "control_gap",
        }
        return mapping[red_flag_type]

    def _kind_from_category(self, category: str) -> ReviewerFindingKind:
        if category == "documentary_gap":
            return ReviewerFindingKind.DOCUMENTARY_GAP
        return ReviewerFindingKind.OPERATIONAL

    def _semantic_key(self, finding: ReviewedFinding) -> tuple[str, str]:
        evidence_text = finding.evidence[0].text if finding.evidence else finding.title
        return (finding.category, self._normalize(evidence_text))

    def _confidence(
        self,
        severity: ReviewerSeverity,
        evidence_count: int,
        source_count: int,
    ) -> float:
        base = {
            ReviewerSeverity.LOW: 0.62,
            ReviewerSeverity.MEDIUM: 0.74,
            ReviewerSeverity.HIGH: 0.84,
        }[severity]
        confidence = base + min(evidence_count - 1, 3) * 0.03
        if source_count > 1:
            confidence += 0.05
        return max(0.0, min(1.0, round(confidence, 2)))

    def _review_required(
        self,
        severity: ReviewerSeverity,
        source_count: int,
    ) -> bool:
        return severity in {ReviewerSeverity.MEDIUM, ReviewerSeverity.HIGH} or source_count > 1

    def _max_severity(
        self,
        left: ReviewerSeverity,
        right: ReviewerSeverity,
    ) -> ReviewerSeverity:
        return left if SEVERITY_RANK[left] >= SEVERITY_RANK[right] else right

    def _severity_from_red_flag(
        self,
        severity: RedFlagSeverity,
    ) -> ReviewerSeverity:
        return ReviewerSeverity(severity.value)

    def _severity_from_accounting_audit(
        self,
        severity: AccountingAuditSeverity,
    ) -> ReviewerSeverity:
        return ReviewerSeverity(severity.value)

    def _merge_unique(self, left: list[str], right: list[str]) -> list[str]:
        merged: list[str] = []
        for value in left + right:
            if value in merged:
                continue
            merged.append(value)
        return merged

    def _document_id(
        self,
        red_flag_output: RedFlagAgentOutput | None,
        accounting_audit_output: AccountingAuditAgentOutput | None,
    ) -> str | None:
        for output in (red_flag_output, accounting_audit_output):
            if output is not None and output.metadata.document_id:
                return output.metadata.document_id
        return None

    def _source_filename(
        self,
        red_flag_output: RedFlagAgentOutput | None,
        accounting_audit_output: AccountingAuditAgentOutput | None,
    ) -> str | None:
        for output in (red_flag_output, accounting_audit_output):
            if output is not None and output.metadata.source_filename:
                return output.metadata.source_filename
        return None

    def _normalize(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
        stop_words = {
            "a",
            "an",
            "the",
            "is",
            "was",
            "were",
            "to",
            "of",
            "for",
            "and",
        }
        return " ".join(
            token for token in normalized.split() if token not in stop_words
        )

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "finding"

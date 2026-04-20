from app.models.report import FindingScore
from app.models.risk import FindingSeverity, FindingSource, Inconsistency, RiskItem


SEVERITY_RANK = {
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
}


class FindingScorer:
    def score_inconsistency(self, finding: Inconsistency) -> FindingScore:
        return self._score(
            severity_hint=finding.severity_hint,
            confidence_hint=finding.confidence_hint,
            source=finding.source,
            evidence_count=len(finding.evidence),
        )

    def score_risk(self, risk: RiskItem) -> FindingScore:
        return self._score(
            severity_hint=risk.severity_hint,
            confidence_hint=risk.confidence_hint,
            source=risk.source,
            evidence_count=len(risk.evidence),
        )

    def _score(
        self,
        severity_hint: FindingSeverity,
        confidence_hint: float,
        source: FindingSource,
        evidence_count: int,
    ) -> FindingScore:
        confidence = confidence_hint
        if source == FindingSource.HYBRID:
            confidence += 0.08
        elif source == FindingSource.HEURISTIC:
            confidence += 0.03

        if evidence_count > 1:
            confidence += 0.04
        if evidence_count == 0:
            confidence -= 0.1

        confidence = max(0.0, min(1.0, round(confidence, 2)))
        severity = severity_hint.value
        review_required = (
            SEVERITY_RANK[severity_hint] >= SEVERITY_RANK[FindingSeverity.MEDIUM]
            or confidence < 0.7
        )

        return FindingScore(
            severity=severity,
            confidence=confidence,
            review_required=review_required,
        )

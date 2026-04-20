from app.models.risk import (
    FindingEvidence,
    FindingSeverity,
    FindingSource,
    Inconsistency,
    InconsistencyType,
)
from app.services.scoring.finding_scorer import FindingScorer


def test_scorer_increases_confidence_for_hybrid_findings_with_evidence() -> None:
    finding = Inconsistency(
        id="finding-1",
        type=InconsistencyType.ACCOUNT_USAGE,
        title="Generic account",
        description="A generic account needs rationale.",
        source=FindingSource.HYBRID,
        severity_hint=FindingSeverity.MEDIUM,
        confidence_hint=0.7,
        evidence=[
            FindingEvidence(source="process", text="clearing account"),
            FindingEvidence(source="knowledge_base", text="needs closure logic"),
        ],
    )

    score = FindingScorer().score_inconsistency(finding)

    assert score.severity == "medium"
    assert score.confidence == 0.82
    assert score.review_required is True


def test_scorer_requires_review_for_low_confidence_low_severity() -> None:
    finding = Inconsistency(
        id="finding-2",
        type=InconsistencyType.DOCUMENTARY_GAP,
        title="Thin documentation",
        description="Documentation is thin.",
        source=FindingSource.LLM,
        severity_hint=FindingSeverity.LOW,
        confidence_hint=0.62,
    )

    score = FindingScorer().score_inconsistency(finding)

    assert score.severity == "low"
    assert score.confidence == 0.52
    assert score.review_required is True

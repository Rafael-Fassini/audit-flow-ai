from app.models.accounting_process import (
    AccountReference,
    AccountReferenceRole,
    AccountingProcess,
    EvidenceSnippet,
    ProcessStep,
    ProcessStepType,
)
from app.models.knowledge_base import KnowledgeCategory, KnowledgeSnippet, RetrievalResult
from app.services.risk_engine.hybrid_inference import HybridRiskInferenceService
from app.services.risk_engine.llm_inference import NoOpLLMRiskInferenceProvider
from app.services.risk_engine.rules import AccountingRiskRules


def test_risk_engine_returns_findings_risks_evidence_and_questions() -> None:
    service = HybridRiskInferenceService(
        rules=AccountingRiskRules(),
        llm_provider=NoOpLLMRiskInferenceProvider(),
    )

    result = service.infer(
        process=AccountingProcess(
            process_name="Suspense entry process",
            summary="The accounting team posts a suspense entry.",
            source_filename="walkthrough.txt",
            steps=[
                ProcessStep(
                    index=0,
                    step_type=ProcessStepType.POSTING,
                    description="The accounting team posts a suspense account entry.",
                    evidence=EvidenceSnippet(
                        section_index=0,
                        chunk_index=0,
                        text="posts a suspense account entry",
                    ),
                )
            ],
            account_references=[
                AccountReference(
                    role=AccountReferenceRole.CREDIT,
                    account_code="2999",
                    account_name="suspense account",
                    evidence=EvidenceSnippet(
                        section_index=0,
                        chunk_index=0,
                        text="credit 2999 suspense account",
                    ),
                )
            ],
        ),
        retrieved_context=[
            RetrievalResult(
                snippet=KnowledgeSnippet(
                    id="suspense-guidance",
                    document_id="guidance",
                    title="Suspense account guidance",
                    text="Suspense accounts require documented closure logic.",
                    category=KnowledgeCategory.CHART_OF_ACCOUNTS,
                    chunk_id="suspense-guidance",
                    raw_text="Suspense accounts require documented closure logic.",
                ),
                score=0.88,
            )
        ],
    )

    assert result.inconsistencies
    assert result.risks
    assert result.follow_up_questions
    assert any(finding.evidence for finding in result.inconsistencies)

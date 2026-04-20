from app.models.accounting_process import (
    AccountReference,
    AccountReferenceRole,
    AccountingProcess,
    EvidenceSnippet,
    ProcessStep,
    ProcessStepType,
)
from app.models.knowledge_base import (
    KnowledgeCategory,
    KnowledgeSnippet,
    RetrievalResult,
)
from app.models.risk import (
    FindingSource,
    FindingSeverity,
    Inconsistency,
    InconsistencyType,
    RiskInferenceResult,
)
from app.services.risk_engine.hybrid_inference import HybridRiskInferenceService
from app.services.risk_engine.llm_inference import LLMRiskInferenceProvider
from app.services.risk_engine.rules import AccountingRiskRules


class FakeLLMRiskInferenceProvider(LLMRiskInferenceProvider):
    def infer(
        self,
        process: AccountingProcess,
        retrieved_context: list[RetrievalResult],
    ) -> RiskInferenceResult:
        return RiskInferenceResult(
            inconsistencies=[
                Inconsistency(
                    id="llm-classification-gap",
                    type=InconsistencyType.CLASSIFICATION,
                    title="Business event and account classification may not align",
                    description=(
                        "The retrieved context expects classification aligned to "
                        "the business event, but the process narrative is thin."
                    ),
                    source=FindingSource.LLM,
                    severity_hint=FindingSeverity.MEDIUM,
                    confidence_hint=0.64,
                    evidence=[],
                )
            ]
        )


def test_hybrid_inference_combines_rules_llm_context_and_questions() -> None:
    service = HybridRiskInferenceService(
        rules=AccountingRiskRules(),
        llm_provider=FakeLLMRiskInferenceProvider(),
    )

    result = service.infer(
        process=_process_with_generic_account(),
        retrieved_context=[_retrieval_result()],
    )

    assert any(finding.source == FindingSource.HYBRID for finding in result.inconsistencies)
    assert any(
        finding.id == "heuristic-generic-account-0"
        for finding in result.inconsistencies
    )
    assert any(
        finding.id == "llm-classification-gap"
        for finding in result.inconsistencies
    )
    assert result.risks
    assert result.follow_up_questions
    assert any(
        evidence.source == "knowledge_base"
        for finding in result.inconsistencies
        for evidence in finding.evidence
    )


def _process_with_generic_account() -> AccountingProcess:
    return AccountingProcess(
        process_name="Clearing account posting",
        summary="The accounting team records clearing account activity.",
        source_filename="walkthrough.txt",
        steps=[
            ProcessStep(
                index=0,
                step_type=ProcessStepType.POSTING,
                description="The accounting team posts to a clearing account.",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="posts to a clearing account",
                ),
            )
        ],
        account_references=[
            AccountReference(
                role=AccountReferenceRole.DEBIT,
                account_code="1999",
                account_name="clearing account",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="debit 1999 clearing account",
                ),
            )
        ],
        posting_logic=["The accounting team posts to a clearing account."],
    )


def _retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        snippet=KnowledgeSnippet(
            id="generic-account-guidance",
            document_id="guidance",
            title="Generic account rationale",
            text="Clearing accounts need rationale and closure logic.",
            category=KnowledgeCategory.CHART_OF_ACCOUNTS,
            chunk_id="generic-account-guidance",
            raw_text="Clearing accounts need rationale and closure logic.",
        ),
        score=0.91,
    )

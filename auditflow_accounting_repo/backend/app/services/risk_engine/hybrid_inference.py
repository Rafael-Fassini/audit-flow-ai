from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import RetrievalResult
from app.models.risk import (
    FindingSource,
    FindingSeverity,
    FollowUpQuestion,
    Inconsistency,
    RiskInferenceResult,
    RiskItem,
)
from app.services.risk_engine.evidence import evidence_from_retrieval_result
from app.services.risk_engine.llm_inference import LLMRiskInferenceProvider
from app.services.risk_engine.rules import AccountingRiskRules


class HybridRiskInferenceService:
    def __init__(
        self,
        rules: AccountingRiskRules,
        llm_provider: LLMRiskInferenceProvider,
    ) -> None:
        self._rules = rules
        self._llm_provider = llm_provider

    def infer(
        self,
        process: AccountingProcess,
        retrieved_context: list[RetrievalResult],
    ) -> RiskInferenceResult:
        heuristic_result = self._rules.evaluate(process)
        llm_result = self._llm_provider.infer(process, retrieved_context)

        inconsistencies = self._merge_inconsistencies(
            heuristic_result.inconsistencies,
            llm_result.inconsistencies,
            retrieved_context,
        )
        risks = self._merge_risks(
            heuristic_result.risks,
            llm_result.risks,
            inconsistencies,
            retrieved_context,
        )
        questions = self._merge_questions(
            heuristic_result.follow_up_questions,
            llm_result.follow_up_questions,
            inconsistencies,
        )

        return RiskInferenceResult(
            inconsistencies=inconsistencies,
            risks=risks,
            follow_up_questions=questions,
        )

    def _merge_inconsistencies(
        self,
        heuristic_findings: list[Inconsistency],
        llm_findings: list[Inconsistency],
        retrieved_context: list[RetrievalResult],
    ) -> list[Inconsistency]:
        findings = self._dedupe_inconsistencies(heuristic_findings + llm_findings)
        knowledge_evidence = [
            evidence_from_retrieval_result(result)
            for result in retrieved_context[:2]
        ]
        if not knowledge_evidence:
            return findings

        enriched: list[Inconsistency] = []
        for finding in findings:
            existing_evidence = list(finding.evidence)
            if finding.source in {FindingSource.HEURISTIC, FindingSource.HYBRID}:
                existing_evidence.extend(knowledge_evidence[:1])
            enriched.append(finding.model_copy(update={"evidence": existing_evidence}))
        return enriched

    def _merge_risks(
        self,
        heuristic_risks: list[RiskItem],
        llm_risks: list[RiskItem],
        inconsistencies: list[Inconsistency],
        retrieved_context: list[RetrievalResult],
    ) -> list[RiskItem]:
        risks_by_id = {risk.id: risk for risk in heuristic_risks}
        for risk in llm_risks:
            risks_by_id.setdefault(risk.id, risk)

        if not risks_by_id and inconsistencies:
            return []

        knowledge_evidence = [
            evidence_from_retrieval_result(result)
            for result in retrieved_context[:1]
        ]
        risks: list[RiskItem] = []
        for risk in risks_by_id.values():
            evidence = list(risk.evidence)
            if knowledge_evidence:
                evidence.extend(knowledge_evidence)
            risks.append(risk.model_copy(update={"evidence": evidence}))
        return risks

    def _merge_questions(
        self,
        heuristic_questions: list[FollowUpQuestion],
        llm_questions: list[FollowUpQuestion],
        inconsistencies: list[Inconsistency],
    ) -> list[FollowUpQuestion]:
        questions_by_id = {
            question.id: question
            for question in heuristic_questions + llm_questions
        }
        for inconsistency in inconsistencies:
            question_id = f"question-{inconsistency.id}"
            if question_id in questions_by_id:
                continue
            questions_by_id[question_id] = FollowUpQuestion(
                id=question_id,
                question=self._question_for_inconsistency(inconsistency),
                rationale=(
                    "The finding needs reviewer confirmation before downstream scoring."
                ),
                related_finding_ids=[inconsistency.id],
            )
        return list(questions_by_id.values())

    def _dedupe_inconsistencies(
        self,
        findings: list[Inconsistency],
    ) -> list[Inconsistency]:
        deduped: list[Inconsistency] = []
        seen: set[tuple[str, str]] = set()
        for finding in findings:
            key = (finding.type.value, finding.title.lower())
            if key in seen:
                continue
            seen.add(key)
            source = finding.source
            if source == FindingSource.LLM:
                source = FindingSource.HYBRID
            deduped.append(finding.model_copy(update={"source": source}))
        return deduped

    def _question_for_inconsistency(self, inconsistency: Inconsistency) -> str:
        if inconsistency.severity_hint == FindingSeverity.HIGH:
            return f"What evidence resolves the high-priority issue: {inconsistency.title}?"
        return f"What documentation supports or resolves this issue: {inconsistency.title}?"

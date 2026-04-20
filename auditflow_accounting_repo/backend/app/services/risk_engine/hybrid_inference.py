from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import RetrievalResult
from app.models.risk import (
    FindingSource,
    FindingSeverity,
    FindingEvidence,
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
        if not retrieved_context:
            return findings

        enriched: list[Inconsistency] = []
        used_knowledge_ids: set[str] = set()
        for finding in findings:
            existing_evidence = list(finding.evidence)
            if finding.source in {FindingSource.HEURISTIC, FindingSource.HYBRID}:
                knowledge_evidence = self._best_knowledge_evidence(
                    finding,
                    retrieved_context,
                    used_knowledge_ids,
                )
                if knowledge_evidence is not None:
                    existing_evidence.append(knowledge_evidence)
                    if knowledge_evidence.knowledge_chunk_id:
                        used_knowledge_ids.add(knowledge_evidence.knowledge_chunk_id)
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

        risks: list[RiskItem] = []
        for risk in risks_by_id.values():
            risks.append(risk.model_copy(update={"evidence": list(risk.evidence)}))
        return self._dedupe_risks(risks)

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
        seen_question_text = {
            self._semantic_text_key(question.question)
            for question in questions_by_id.values()
        }
        for inconsistency in inconsistencies:
            question_id = f"question-{inconsistency.id}"
            if question_id in questions_by_id:
                continue
            question_text = self._question_for_inconsistency(inconsistency)
            question_key = self._semantic_text_key(question_text)
            if question_key in seen_question_text:
                continue
            seen_question_text.add(question_key)
            questions_by_id[question_id] = FollowUpQuestion(
                id=question_id,
                question=question_text,
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
        seen: set[str] = set()
        for finding in findings:
            key = self._finding_semantic_key(finding)
            if key in seen:
                continue
            seen.add(key)
            source = finding.source
            if source == FindingSource.LLM:
                source = FindingSource.HYBRID
            deduped.append(finding.model_copy(update={"source": source}))
        return deduped

    def _dedupe_risks(self, risks: list[RiskItem]) -> list[RiskItem]:
        deduped: list[RiskItem] = []
        seen: set[str] = set()
        for risk in risks:
            key = f"{risk.category.value}:{self._semantic_text_key(risk.title)}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(risk)
        return deduped

    def _best_knowledge_evidence(
        self,
        finding: Inconsistency,
        retrieved_context: list[RetrievalResult],
        used_knowledge_ids: set[str],
    ) -> FindingEvidence | None:
        finding_text = f"{finding.title} {finding.description}"
        finding_tokens = set(self._tokens(finding_text))
        if len(finding_tokens) < 4:
            return None

        for result in retrieved_context:
            snippet = result.snippet
            chunk_id = snippet.chunk_id or snippet.id
            if chunk_id in used_knowledge_ids:
                continue
            snippet_tokens = set(self._tokens(snippet.text))
            overlap = finding_tokens.intersection(snippet_tokens)
            if len(overlap) < 2:
                continue
            return evidence_from_retrieval_result(result)
        return None

    def _finding_semantic_key(self, finding: Inconsistency) -> str:
        text = self._normalize(f"{finding.title} {finding.description}")
        if "traceability" in text or "rastreabilidade" in text:
            return "traceability-limitation"
        if "third-party" in text or "third party" in text or "terceir" in text:
            return "third-party-dependency"
        if "accounting-entry details" in text or "not identify" in text:
            return "missing-accounting-entry-details"
        if "control" in text or "controle" in text or "fragilidade" in text:
            return "control-weakness"
        if "inconsist" in text or "diverg" in text:
            return "operational-inconsistency"
        return f"{finding.type.value}:{self._semantic_text_key(text)}"

    def _tokens(self, value: str) -> list[str]:
        stop_words = {
            "a",
            "o",
            "os",
            "as",
            "de",
            "do",
            "da",
            "dos",
            "das",
            "e",
            "para",
            "com",
            "the",
            "and",
            "of",
            "to",
            "is",
            "are",
            "this",
            "that",
        }
        return [
            token
            for token in self._normalize(value).replace("-", " ").split()
            if len(token) > 2 and token not in stop_words
        ]

    def _semantic_text_key(self, value: str) -> str:
        return " ".join(self._tokens(value)[:12])

    def _normalize(self, value: str) -> str:
        normalized = value.lower()
        replacements = {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ç": "c",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return " ".join(normalized.split())

    def _question_for_inconsistency(self, inconsistency: Inconsistency) -> str:
        combined_text = f"{inconsistency.title} {inconsistency.description}".lower()
        if "traceability" in combined_text or "rastreabilidade" in combined_text:
            return (
                "Which source records, reconciliations, and audit trail evidence "
                "support end-to-end traceability for this process?"
            )
        if "third-party" in combined_text or "third party" in combined_text or "terceir" in combined_text:
            return (
                "Which controls validate information received from third parties "
                "before it is used in accounting or operational reporting?"
            )
        if (
            "control" in combined_text
            or "controle" in combined_text
            or "fragilidade" in combined_text
            or "limita" in combined_text
        ):
            return (
                "What control evidence demonstrates that this limitation is monitored, "
                "reviewed, and remediated?"
            )
        if "inconsist" in combined_text or "diverg" in combined_text:
            return (
                "What reconciliation or exception-handling evidence resolves the "
                "operational inconsistency described in the narrative?"
            )
        if inconsistency.severity_hint == FindingSeverity.HIGH:
            return f"What evidence resolves the high-priority issue: {inconsistency.title}?"
        return f"What documentation supports or resolves this issue: {inconsistency.title}?"

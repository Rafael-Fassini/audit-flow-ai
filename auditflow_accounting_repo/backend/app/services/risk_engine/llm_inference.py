from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import RetrievalResult
from app.models.risk import RiskInferenceResult


class LLMRiskInferenceProvider:
    def infer(
        self,
        process: AccountingProcess,
        retrieved_context: list[RetrievalResult],
    ) -> RiskInferenceResult:
        raise NotImplementedError


class NoOpLLMRiskInferenceProvider(LLMRiskInferenceProvider):
    def infer(
        self,
        process: AccountingProcess,
        retrieved_context: list[RetrievalResult],
    ) -> RiskInferenceResult:
        return RiskInferenceResult()

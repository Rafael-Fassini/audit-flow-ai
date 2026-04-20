from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import (
    DocumentFamily,
    DocumentScope,
    KnowledgeSnippet,
    RetrievalResult,
)
from app.services.retrieval.embeddings import EmbeddingProvider
from app.services.retrieval.vector_store import VectorStore


class KnowledgeRetrievalService:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        collection_name: str,
        default_limit: int = 5,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._collection_name = collection_name
        self._default_limit = default_limit

    def retrieve_for_query(
        self,
        query: str,
        limit: int | None = None,
        metadata_filter: dict[str, str] | None = None,
        preferred_document_scope: str | None = None,
        preferred_regime_applicability: str | None = None,
        allowed_document_families: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> list[RetrievalResult]:
        result_limit = limit or self._default_limit
        allowed_family_values = set(allowed_document_families or [])
        query_vector = self._embedding_provider.embed(query)
        search_results = self._vector_store.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=result_limit * 3,
            metadata_filter=metadata_filter,
        )
        results = [
            RetrievalResult(
                snippet=KnowledgeSnippet.model_validate(result.payload["snippet"]),
                score=self._adjust_score(
                    result.score,
                    KnowledgeSnippet.model_validate(result.payload["snippet"]),
                    query,
                    preferred_document_scope,
                    preferred_regime_applicability,
                    metadata_filter,
                ),
            )
            for result in search_results
            if "snippet" in result.payload
            and self._is_allowed_family(
                KnowledgeSnippet.model_validate(result.payload["snippet"]),
                allowed_family_values,
            )
        ]
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:result_limit]

    def retrieve_for_process(
        self,
        process: AccountingProcess,
        limit: int | None = None,
        metadata_filter: dict[str, str] | None = None,
        preferred_document_scope: str | None = None,
        preferred_regime_applicability: str | None = None,
        allowed_document_families: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> list[RetrievalResult]:
        return self.retrieve_for_query(
            query=self._query_from_process(process),
            limit=limit,
            metadata_filter=metadata_filter,
            preferred_document_scope=preferred_document_scope,
            preferred_regime_applicability=preferred_regime_applicability,
            allowed_document_families=allowed_document_families,
        )

    def _query_from_process(self, process: AccountingProcess) -> str:
        account_terms = " ".join(
            f"{account.role.value} {account.account_code or ''} {account.account_name}"
            for account in process.account_references
        )
        controls = " ".join(control.description for control in process.controls)
        posting_logic = " ".join(process.posting_logic)
        chart_references = " ".join(
            reference.reference_text
            for reference in process.chart_of_accounts_references
        )
        return " ".join(
            part
            for part in (
                process.process_name,
                process.summary,
                account_terms,
                posting_logic,
                controls,
                chart_references,
            )
            if part
        )

    def _adjust_score(
        self,
        score: float,
        snippet: KnowledgeSnippet,
        query: str,
        preferred_document_scope: str | None,
        preferred_regime_applicability: str | None,
        metadata_filter: dict[str, str] | None,
    ) -> float:
        adjusted = score
        if preferred_document_scope and snippet.document_scope == preferred_document_scope:
            adjusted += 0.08
        if (
            preferred_regime_applicability
            and snippet.regime_applicability == preferred_regime_applicability
        ):
            adjusted += 0.08
        if not metadata_filter and self._is_general_query(query):
            if snippet.document_family == DocumentFamily.DERE:
                adjusted -= 0.12
            if snippet.document_scope == DocumentScope.REGIME_ESPECIFICO:
                adjusted -= 0.12
        return max(0.0, min(1.0, adjusted))

    def _is_general_query(self, query: str) -> bool:
        lower_query = query.lower()
        regime_terms = {
            "dere",
            "regime específico",
            "regimes específicos",
            "serviços financeiros",
            "financeiro",
            "saúde",
            "prognóstico",
            "prognosticos",
        }
        if any(term in lower_query for term in regime_terms):
            return False
        return True

    def _is_allowed_family(
        self,
        snippet: KnowledgeSnippet,
        allowed_family_values: set[str],
    ) -> bool:
        if not allowed_family_values:
            return True
        return snippet.document_family.value in allowed_family_values

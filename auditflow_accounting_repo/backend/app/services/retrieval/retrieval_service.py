from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import KnowledgeSnippet, RetrievalResult
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
    ) -> list[RetrievalResult]:
        query_vector = self._embedding_provider.embed(query)
        search_results = self._vector_store.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            limit=limit or self._default_limit,
        )
        return [
            RetrievalResult(
                snippet=KnowledgeSnippet.model_validate(result.payload["snippet"]),
                score=result.score,
            )
            for result in search_results
            if "snippet" in result.payload
        ]

    def retrieve_for_process(
        self,
        process: AccountingProcess,
        limit: int | None = None,
    ) -> list[RetrievalResult]:
        return self.retrieve_for_query(
            query=self._query_from_process(process),
            limit=limit,
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

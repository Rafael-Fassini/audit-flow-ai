import pytest

from app.models.accounting_process import (
    AccountReference,
    AccountReferenceRole,
    AccountingProcess,
    EvidenceSnippet,
)
from app.models.knowledge_base import (
    DocumentFamily,
    DocumentScope,
    AuthorityLevel,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeSnippet,
    RegimeApplicability,
)
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.curated_knowledge import default_knowledge_documents
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.vector_store import InMemoryVectorStore, VectorPoint


def test_indexer_indexes_curated_knowledge_snippets() -> None:
    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    indexer = KnowledgeIndexer(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name="knowledge",
    )

    indexed_count = indexer.index_documents([_knowledge_document()])

    assert indexed_count == 3


def test_default_knowledge_base_contains_indexable_mvp_guidance() -> None:
    documents = default_knowledge_documents()

    assert documents
    assert sum(len(document.snippets) for document in documents) >= 3
    assert any(
        "chart" in snippet.text.lower() or "account" in snippet.text.lower()
        for document in documents
        for snippet in document.snippets
    )


def test_retrieval_returns_relevant_context_for_query() -> None:
    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    collection_name = "knowledge"
    KnowledgeIndexer(vector_store, embedding_provider, collection_name).index_documents(
        [_knowledge_document()]
    )
    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
        default_limit=2,
    )

    results = retrieval_service.retrieve_for_query(
        "clearing account reconciliation and closure",
    )

    assert len(results) == 2
    assert results[0].snippet.id == "clearing-account-review"
    assert results[0].score > 0


def test_retrieval_builds_query_from_accounting_process() -> None:
    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    collection_name = "knowledge"
    KnowledgeIndexer(vector_store, embedding_provider, collection_name).index_documents(
        [_knowledge_document()]
    )
    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
        default_limit=1,
    )
    process = AccountingProcess(
        process_name="Accrual posting",
        summary="The accounting team records accrued liabilities.",
        source_filename="walkthrough.txt",
        account_references=[
            AccountReference(
                role=AccountReferenceRole.CREDIT,
                account_code="2100",
                account_name="accrued liabilities",
                evidence=EvidenceSnippet(
                    section_index=0,
                    chunk_index=0,
                    text="credit accrued liabilities",
                ),
            )
        ],
        posting_logic=["credit accrued liabilities after invoice estimate"],
    )

    results = retrieval_service.retrieve_for_process(process)

    assert len(results) == 1
    assert results[0].snippet.id == "accrued-liability-support"


def test_vector_store_rejects_wrong_vector_size() -> None:
    vector_store = InMemoryVectorStore()
    vector_store.ensure_collection(collection_name="knowledge", vector_size=3)

    with pytest.raises(ValueError):
        vector_store.upsert(
            "knowledge",
            [
                VectorPoint(
                    id="bad-vector",
                    vector=[1.0, 0.0],
                    payload={},
                )
            ],
        )


def test_retrieval_filters_and_prioritizes_by_scope_metadata() -> None:
    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    collection_name = "knowledge"
    KnowledgeIndexer(vector_store, embedding_provider, collection_name).index_documents(
        [_scoped_knowledge_document()]
    )
    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
        default_limit=2,
    )

    general_results = retrieval_service.retrieve_for_query("account classification rule")
    dere_results = retrieval_service.retrieve_for_query(
        "account classification rule DeRE",
        metadata_filter={"document_family": DocumentFamily.DERE.value},
        preferred_document_scope=DocumentScope.REGIME_ESPECIFICO.value,
    )

    assert general_results[0].snippet.document_family != DocumentFamily.DERE
    assert dere_results
    assert all(result.snippet.document_family == DocumentFamily.DERE for result in dere_results)


def _knowledge_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="accounting-guidance",
        title="Accounting entry guidance",
        source="curated MVP guidance",
        category=KnowledgeCategory.POSTING_GUIDANCE,
        snippets=[
            KnowledgeSnippet(
                id="clearing-account-review",
                document_id="accounting-guidance",
                title="Clearing account review",
                text=(
                    "Clearing account balances should have documented "
                    "reconciliation, aging review, and closure logic."
                ),
                category=KnowledgeCategory.CHART_OF_ACCOUNTS,
                tags=["clearing", "reconciliation"],
            ),
            KnowledgeSnippet(
                id="accrued-liability-support",
                document_id="accounting-guidance",
                title="Accrued liability support",
                text=(
                    "Accrued liabilities require support for the estimate "
                    "and clear credit posting rationale."
                ),
                category=KnowledgeCategory.POSTING_GUIDANCE,
                tags=["accrual", "liability"],
            ),
            KnowledgeSnippet(
                id="approval-control",
                document_id="accounting-guidance",
                title="Approval control",
                text="Journal entries should be approved before posting to the ledger.",
                category=KnowledgeCategory.CONTROL_GUIDANCE,
                tags=["approval", "control"],
            ),
        ],
    )


def _scoped_knowledge_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="scoped-guidance",
        title="Scoped guidance",
        source="test",
        category=KnowledgeCategory.POSTING_GUIDANCE,
        snippets=[
            KnowledgeSnippet(
                id="general-classification",
                document_id="scoped-guidance",
                title="General account classification",
                text="Account classification rule for general accounting context.",
                category=KnowledgeCategory.ACCOUNTING_POLICY,
                document_family=DocumentFamily.REFORMA_TRIBUTARIA,
                document_scope=DocumentScope.NORMA_GERAL,
                authority_level=AuthorityLevel.LEI,
                regime_applicability=RegimeApplicability.GERAL,
                source_file="LCP_214.pdf",
                source_archive="kb.zip",
                chunk_id="general-classification",
                raw_text="Account classification rule for general accounting context.",
            ),
            KnowledgeSnippet(
                id="dere-classification",
                document_id="scoped-guidance",
                title="DeRE account classification",
                text="Account classification rule for DeRE regime specific context.",
                category=KnowledgeCategory.POSTING_GUIDANCE,
                document_family=DocumentFamily.DERE,
                document_scope=DocumentScope.REGIME_ESPECIFICO,
                authority_level=AuthorityLevel.MANUAL,
                regime_applicability=RegimeApplicability.SERV_FIN,
                source_file="Manual Usuario DeRE.pdf",
                source_archive="kb.zip",
                chunk_id="dere-classification",
                raw_text="Account classification rule for DeRE regime specific context.",
            ),
        ],
    )

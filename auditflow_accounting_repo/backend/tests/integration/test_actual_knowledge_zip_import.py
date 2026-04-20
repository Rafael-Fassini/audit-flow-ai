from pathlib import Path

from app.models.knowledge_base import DocumentFamily, DocumentScope
from app.services.chunking.document_chunker import DocumentChunker
from app.services.parsing.document_parser import DocumentParser
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.knowledge_zip_importer import KnowledgeZipImporter
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.vector_store import InMemoryVectorStore


def test_actual_recommended_zip_imports_and_retrieves_scoped_chunks() -> None:
    archive_path = (
        Path(__file__).resolve().parents[2]
        / "knowledge_base"
        / "imports"
        / "recommended_kb_docs_package_atualizado.zip"
    )
    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=64)
    collection_name = "knowledge"
    importer = KnowledgeZipImporter(
        parser=DocumentParser(),
        chunker=DocumentChunker(max_chunk_chars=1800),
        indexer=KnowledgeIndexer(vector_store, embedding_provider, collection_name),
    )

    report = importer.import_zip(archive_path)

    assert report.indexed_chunks > 0
    assert any("LCP_214(1).pdf" in path for path in report.duplicate_files)
    assert any(path.endswith(".md") for path in report.unsupported_files)

    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
        default_limit=3,
    )
    lc_214_results = retrieval_service.retrieve_for_query(
        "IBS CBS imposto seletivo reforma tributaria",
        metadata_filter={"document_family": DocumentFamily.LC_214_2025.value},
    )
    dere_results = retrieval_service.retrieve_for_query(
        "DeRE leiaute eventos regimes especificos",
        metadata_filter={"document_scope": DocumentScope.REGIME_ESPECIFICO.value},
    )
    general_results = retrieval_service.retrieve_for_query(
        "IBS CBS norma geral reforma tributaria",
    )

    assert lc_214_results
    assert lc_214_results[0].snippet.source_archive == archive_path.name
    assert lc_214_results[0].snippet.raw_text
    assert dere_results == []
    assert general_results[0].snippet.document_family != DocumentFamily.DERE

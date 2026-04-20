from pathlib import Path
from zipfile import ZipFile

from app.models.knowledge_base import DocumentFamily, DocumentScope
from app.services.chunking.document_chunker import DocumentChunker
from app.services.parsing.document_parser import DocumentParser
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.knowledge_zip_importer import KnowledgeZipImporter
from app.services.retrieval.retrieval_service import KnowledgeRetrievalService
from app.services.retrieval.vector_store import InMemoryVectorStore


def test_zip_importer_parses_chunks_indexes_and_deduplicates(tmp_path: Path) -> None:
    archive_path = tmp_path / "kb.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "docs/LCP_214.txt",
            "LCP 214 defines IBS CBS and general tax reform rules.",
        )
        archive.writestr(
            "docs/LCP_214_copy.txt",
            "LCP 214 defines IBS CBS and general tax reform rules.",
        )
        archive.writestr(
            "docs/Manual Usuario DeRE.txt",
            "DeRE regime specific manual for financial services.",
        )
        archive.writestr("docs/README.md", "unsupported")

    vector_store = InMemoryVectorStore()
    embedding_provider = DeterministicEmbeddingProvider(vector_size=32)
    collection_name = "knowledge"
    importer = KnowledgeZipImporter(
        parser=DocumentParser(),
        chunker=DocumentChunker(max_chunk_chars=200),
        indexer=KnowledgeIndexer(vector_store, embedding_provider, collection_name),
    )

    report = importer.import_zip(archive_path)

    assert report.indexed_chunks == 2
    assert report.duplicate_files == ["docs/LCP_214_copy.txt"]
    assert report.unsupported_files == ["docs/README.md"]
    assert not report.failed_files

    retrieval_service = KnowledgeRetrievalService(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        collection_name=collection_name,
    )
    lc_214_results = retrieval_service.retrieve_for_query(
        "IBS CBS reforma tributaria",
        metadata_filter={"document_family": DocumentFamily.LC_214_2025.value},
    )
    dere_results = retrieval_service.retrieve_for_query(
        "DeRE financial services",
        metadata_filter={"document_scope": DocumentScope.REGIME_ESPECIFICO.value},
    )

    assert lc_214_results
    assert lc_214_results[0].snippet.source_archive == "kb.zip"
    assert lc_214_results[0].snippet.source_file == "docs/LCP_214.txt"
    assert lc_214_results[0].snippet.chunk_id
    assert lc_214_results[0].snippet.raw_text
    assert dere_results == []

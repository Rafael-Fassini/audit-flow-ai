import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from qdrant_client import QdrantClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.chunking.document_chunker import DocumentChunker
from app.services.parsing.document_parser import DocumentParser
from app.services.retrieval.embeddings import DeterministicEmbeddingProvider
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer
from app.services.retrieval.knowledge_zip_importer import KnowledgeZipImporter
from app.services.retrieval.vector_store import QdrantVectorStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a knowledge-base zip.")
    parser.add_argument("archive_path", type=Path)
    args = parser.parse_args()

    qdrant_client = QdrantClient(url=settings.qdrant_url)
    embedding_provider = DeterministicEmbeddingProvider(
        vector_size=settings.embedding_vector_size
    )
    indexer = KnowledgeIndexer(
        vector_store=QdrantVectorStore(qdrant_client),
        embedding_provider=embedding_provider,
        collection_name=settings.knowledge_collection_name,
    )
    importer = KnowledgeZipImporter(
        parser=DocumentParser(),
        chunker=DocumentChunker(),
        indexer=indexer,
    )

    report = importer.import_zip(args.archive_path)
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

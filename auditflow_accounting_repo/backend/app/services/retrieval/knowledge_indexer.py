from app.models.knowledge_base import KnowledgeDocument, KnowledgeSnippet
from app.services.retrieval.embeddings import EmbeddingProvider
from app.services.retrieval.vector_store import VectorPoint, VectorStore


class KnowledgeIndexer:
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        collection_name: str,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._collection_name = collection_name

    def index_documents(self, documents: list[KnowledgeDocument]) -> int:
        self._vector_store.ensure_collection(
            collection_name=self._collection_name,
            vector_size=self._embedding_provider.vector_size,
        )

        points: list[VectorPoint] = []
        for document in documents:
            for snippet in document.snippets:
                points.append(
                    VectorPoint(
                        id=snippet.id,
                        vector=self._embedding_provider.embed(snippet.text),
                        payload=self._payload_for(document, snippet),
                    )
                )

        if points:
            self._vector_store.upsert(self._collection_name, points)
        return len(points)

    def _payload_for(
        self,
        document: KnowledgeDocument,
        snippet: KnowledgeSnippet,
    ) -> dict[str, object]:
        return {
            "snippet": snippet.model_dump(mode="json"),
            "document": {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "category": document.category.value,
            },
        }

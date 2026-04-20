from app.models.knowledge_base import RetrievalResult
from app.models.risk import FindingEvidence


def evidence_from_retrieval_result(result: RetrievalResult) -> FindingEvidence:
    snippet = result.snippet
    return FindingEvidence(
        source="knowledge_base",
        text=snippet.raw_text or snippet.text,
        knowledge_chunk_id=snippet.chunk_id,
        document_family=snippet.document_family.value,
        document_scope=snippet.document_scope.value,
    )

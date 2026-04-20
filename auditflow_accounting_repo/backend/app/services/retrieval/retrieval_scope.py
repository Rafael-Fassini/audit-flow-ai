from app.models.knowledge_base import DocumentFamily


APPROVED_RETRIEVAL_DOCUMENT_FAMILIES: tuple[DocumentFamily, ...] = (
    DocumentFamily.NBC_TG_CPC_00_R2,
    DocumentFamily.LC_214_2025,
)


def approved_retrieval_family_values() -> set[str]:
    return {family.value for family in APPROVED_RETRIEVAL_DOCUMENT_FAMILIES}

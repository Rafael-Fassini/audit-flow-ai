from app.models.knowledge_base import (
    DocumentFamily,
    DocumentScope,
    AuthorityLevel,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeSnippet,
    RegimeApplicability,
)


def default_knowledge_documents() -> list[KnowledgeDocument]:
    return [
        KnowledgeDocument(
            id="accounting-entry-guidance",
            title="Accounting entry and chart-of-accounts guidance",
            source="auditflow-mvp-curated-guidance",
            category=KnowledgeCategory.POSTING_GUIDANCE,
            snippets=[
                KnowledgeSnippet(
                    id="generic-account-rationale",
                    document_id="accounting-entry-guidance",
                    title="Generic account rationale",
                    text=(
                        "Generic, clearing, suspense, and transitional accounts "
                        "should have documented rationale, expected closure logic, "
                        "and owner review."
                    ),
                    category=KnowledgeCategory.CHART_OF_ACCOUNTS,
                    tags=["chart-of-accounts", "clearing", "suspense"],
                    document_family=DocumentFamily.NBC_TG_CPC_00_R2,
                    document_scope=DocumentScope.NORMA_GERAL,
                    authority_level=AuthorityLevel.LEI,
                    regime_applicability=RegimeApplicability.GERAL,
                ),
                KnowledgeSnippet(
                    id="posting-business-event-alignment",
                    document_id="accounting-entry-guidance",
                    title="Posting and business event alignment",
                    text=(
                        "The selected debit and credit accounts should align with "
                        "the described business event and account classification "
                        "policy."
                    ),
                    category=KnowledgeCategory.POSTING_GUIDANCE,
                    tags=["posting", "classification"],
                    document_family=DocumentFamily.NBC_TG_CPC_00_R2,
                    document_scope=DocumentScope.NORMA_GERAL,
                    authority_level=AuthorityLevel.LEI,
                    regime_applicability=RegimeApplicability.GERAL,
                ),
                KnowledgeSnippet(
                    id="journal-entry-support-control",
                    document_id="accounting-entry-guidance",
                    title="Journal entry support control",
                    text=(
                        "Journal entries should include supporting evidence, "
                        "approval before posting, and review of the account usage."
                    ),
                    category=KnowledgeCategory.CONTROL_GUIDANCE,
                    tags=["approval", "evidence", "control"],
                    document_family=DocumentFamily.NBC_TG_CPC_00_R2,
                    document_scope=DocumentScope.NORMA_GERAL,
                    authority_level=AuthorityLevel.LEI,
                    regime_applicability=RegimeApplicability.GERAL,
                ),
            ],
        )
    ]

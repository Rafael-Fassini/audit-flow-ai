from app.models.accounting_process import AccountingProcess
from app.models.document_section import DocumentFormat, ParsedDocument
from app.models.knowledge_base import DocumentFamily
from app.services.analysis.product_scope import (
    ProductScopePolicy,
    ScopeStatus,
    SupportedDocumentType,
)


def test_product_scope_accepts_approved_memo_document_type() -> None:
    policy = ProductScopePolicy()

    assessment = policy.assess(
        parsed_document=ParsedDocument(
            filename="insurance_broker_memo.txt",
            document_format=DocumentFormat.TXT,
            text=(
                "Memorando Walkthrough Corretora. O documento descreve aprovação, "
                "pagamento, evidências e registro contábil."
            ),
        ),
        process=AccountingProcess(
            process_name="Processo operacional e contábil de corretora",
            summary="Walkthrough de documentação, aprovação e registro contábil.",
            source_filename="insurance_broker_memo.txt",
        ),
    )

    assert assessment.status == ScopeStatus.IN_SCOPE
    assert assessment.document_type == SupportedDocumentType.WALKTHROUGH
    assert assessment.approved_normative_families == [
        DocumentFamily.NBC_TG_CPC_00_R2,
        DocumentFamily.LC_214_2025,
    ]


def test_product_scope_rejects_broad_audit_or_tax_work() -> None:
    assessment = ProductScopePolicy().assess(
        parsed_document=ParsedDocument(
            filename="tax_opinion.txt",
            document_format=DocumentFormat.TXT,
            text=(
                "Prepare a full audit and broad legal interpretation with tax "
                "calculation for all reform impacts."
            ),
        ),
        process=AccountingProcess(
            process_name="Tax opinion",
            summary="Full audit and tax calculation request.",
            source_filename="tax_opinion.txt",
        ),
    )

    assert assessment.status == ScopeStatus.OUT_OF_SCOPE
    assert assessment.document_type is None
    assert "tax calculations" in assessment.reason


def test_product_scope_rejects_unrelated_document_types() -> None:
    assessment = ProductScopePolicy().assess(
        parsed_document=ParsedDocument(
            filename="marketing_plan.txt",
            document_format=DocumentFormat.TXT,
            text="Campaign goals, channels, audience segments, and brand messaging.",
        ),
        process=AccountingProcess(
            process_name="Marketing plan",
            summary="Campaign goals and audience segments.",
            source_filename="marketing_plan.txt",
        ),
    )

    assert assessment.status == ScopeStatus.OUT_OF_SCOPE
    assert "memoranda" in assessment.reason

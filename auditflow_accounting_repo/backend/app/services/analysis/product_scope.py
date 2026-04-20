import re
from enum import Enum

from pydantic import BaseModel, Field

from app.models.accounting_process import AccountingProcess
from app.models.document_section import ParsedDocument
from app.models.knowledge_base import DocumentFamily
from app.services.retrieval.retrieval_scope import APPROVED_RETRIEVAL_DOCUMENT_FAMILIES


class SupportedDocumentType(str, Enum):
    MEMORANDUM = "memorandum"
    WALKTHROUGH = "walkthrough"
    PAYMENT_SUPPORT = "payment_support"
    ACCOUNTING_ENTRY_SUPPORT = "accounting_entry_support"


class ScopeStatus(str, Enum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"


class ProductScopeAssessment(BaseModel):
    status: ScopeStatus
    document_type: SupportedDocumentType | None = None
    reason: str = Field(min_length=1)
    approved_normative_families: list[DocumentFamily] = Field(default_factory=list)
    normative_focus: list[str] = Field(default_factory=list)

    @property
    def is_in_scope(self) -> bool:
        return self.status == ScopeStatus.IN_SCOPE


class ProductScopePolicy:
    APPROVED_NORMATIVE_FAMILIES = (
        *APPROVED_RETRIEVAL_DOCUMENT_FAMILIES,
    )
    NORMATIVE_FOCUS = (
        "NBC TG / CPC 00 (R2) for documentation, evidence, traceability, and accounting support.",
        "LC 214/2025 only within the delimited support-document and accounting-impact scope.",
    )

    _SUPPORTED_PATTERNS: tuple[tuple[SupportedDocumentType, tuple[str, ...]], ...] = (
        (
            SupportedDocumentType.WALKTHROUGH,
            (
                "walkthrough",
                "walk-through",
                "fluxo operacional",
                "process walkthrough",
            ),
        ),
        (
            SupportedDocumentType.PAYMENT_SUPPORT,
            (
                "payment",
                "pagamento",
                "invoice",
                "nota fiscal",
                "fatura",
                "purchase order",
                "ordem de compra",
            ),
        ),
        (
            SupportedDocumentType.ACCOUNTING_ENTRY_SUPPORT,
            (
                "accounting entry",
                "journal entry",
                "lançamento contábil",
                "lancamento contabil",
                "registro contábil",
                "registro contabil",
                "posting",
            ),
        ),
        (
            SupportedDocumentType.MEMORANDUM,
            (
                "memorandum",
                "memorando",
                "memo",
            ),
        ),
    )
    _OUT_OF_SCOPE_PATTERNS = (
        "tax calculation",
        "calcular tributo",
        "calculo tributario",
        "cálculo tributário",
        "legal opinion",
        "parecer jurídico",
        "parecer juridico",
        "broad legal interpretation",
        "interpretação legal ampla",
        "interpretacao legal ampla",
        "full audit",
        "auditoria completa",
        "unrestricted reform",
        "reforma tributária ampla",
        "reforma tributaria ampla",
    )

    def assess(
        self,
        parsed_document: ParsedDocument,
        process: AccountingProcess,
    ) -> ProductScopeAssessment:
        delimited_text = self._normalize(
            " ".join(
                (
                    parsed_document.filename,
                    parsed_document.text[:5000],
                    process.process_name,
                    process.summary,
                )
            )
        )
        out_of_scope_reason = self._out_of_scope_reason(delimited_text)
        if out_of_scope_reason:
            return ProductScopeAssessment(
                status=ScopeStatus.OUT_OF_SCOPE,
                reason=out_of_scope_reason,
                normative_focus=list(self.NORMATIVE_FOCUS),
            )

        document_type = self._classify_supported_document(delimited_text)
        if document_type is None:
            return ProductScopeAssessment(
                status=ScopeStatus.OUT_OF_SCOPE,
                reason=(
                    "The document is outside the supported product scope. "
                    "AuditFlow supports memoranda, walkthroughs, payment support, "
                    "and accounting-entry support documents only."
                ),
                normative_focus=list(self.NORMATIVE_FOCUS),
            )

        return ProductScopeAssessment(
            status=ScopeStatus.IN_SCOPE,
            document_type=document_type,
            reason=(
                "Document matches the approved AuditFlow support scope for "
                "documentation, approval, value, classification, traceability, "
                "and scoped normative review."
            ),
            approved_normative_families=list(self.APPROVED_NORMATIVE_FAMILIES),
            normative_focus=list(self.NORMATIVE_FOCUS),
        )

    def allowed_document_family_values(self) -> set[str]:
        return {family.value for family in self.APPROVED_NORMATIVE_FAMILIES}

    def _classify_supported_document(
        self,
        normalized_text: str,
    ) -> SupportedDocumentType | None:
        for document_type, patterns in self._SUPPORTED_PATTERNS:
            if any(pattern in normalized_text for pattern in patterns):
                return document_type
        return None

    def _out_of_scope_reason(self, normalized_text: str) -> str | None:
        if not any(pattern in normalized_text for pattern in self._OUT_OF_SCOPE_PATTERNS):
            return None
        return (
            "The document asks for work outside the approved product scope. "
            "The system does not perform tax calculations, broad legal interpretation, "
            "unrestricted reform analysis, or full audit opinions."
        )

    def _normalize(self, value: str) -> str:
        normalized = value.lower()
        replacements = {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ç": "c",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return re.sub(r"\s+", " ", normalized).strip()

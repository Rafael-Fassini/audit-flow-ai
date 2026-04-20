import json
import re
from typing import Protocol

from pydantic import ValidationError

from app.agents.prompts.accounting_audit import build_accounting_audit_prompt
from app.agents.prompts.base import PromptPayload
from app.models.document import DocumentMetadata
from app.models.document_section import ParsedDocument
from app.schemas.agents import (
    AccountingAuditAgentOutput,
    AccountingAuditCandidateFinding,
    AccountingAuditCategory,
    AccountingAuditEvidence,
    AccountingAuditSeverity,
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    DocumentUnderstandingResult,
)


class AccountingAuditModelProvider(Protocol):
    def generate(self, prompt: PromptPayload) -> dict | str:
        raise NotImplementedError


class AccountingAuditAgent:
    def __init__(
        self,
        model_provider: AccountingAuditModelProvider | None = None,
    ) -> None:
        self._model_provider = model_provider

    def classify(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
        understanding: DocumentUnderstandingResult | None = None,
        analysis_id: str | None = None,
    ) -> AccountingAuditAgentOutput:
        prompt = build_accounting_audit_prompt(
            parsed_document=parsed_document,
            document_metadata=document_metadata,
            understanding=understanding,
        )
        if self._model_provider is not None:
            try:
                provider_output = self._model_provider.generate(prompt)
                if isinstance(provider_output, str):
                    provider_output = json.loads(provider_output)
                output = AccountingAuditAgentOutput.model_validate(provider_output)
                self._validate_output_references(output, parsed_document.text)
                return output
            except (TypeError, ValueError, ValidationError, json.JSONDecodeError):
                return AccountingAuditAgentOutput(
                    metadata=self._metadata(
                        document_metadata=document_metadata,
                        analysis_id=analysis_id,
                        status=AgentOutputStatus.NEEDS_REVIEW,
                        errors=[
                            AgentError(
                                code="invalid_accounting_audit_model_output",
                                message=(
                                    "Accounting audit model output did not validate or "
                                    "cited unsupported evidence; deterministic fallback "
                                    "was used."
                                ),
                                retryable=True,
                            )
                        ],
                    ),
                    findings=self._fallback_findings(parsed_document.text),
                )

        return AccountingAuditAgentOutput(
            metadata=self._metadata(
                document_metadata=document_metadata,
                analysis_id=analysis_id,
                status=AgentOutputStatus.COMPLETED,
            ),
            findings=self._fallback_findings(parsed_document.text),
        )

    def _metadata(
        self,
        document_metadata: DocumentMetadata,
        analysis_id: str | None,
        status: AgentOutputStatus,
        errors: list[AgentError] | None = None,
    ) -> AgentOutputMetadata:
        return AgentOutputMetadata(
            agent_role=AgentRole.ACCOUNTING_AUDIT,
            status=status,
            analysis_id=analysis_id,
            document_id=document_metadata.id,
            source_filename=document_metadata.original_filename,
            errors=errors or [],
        )

    def _fallback_findings(self, text: str) -> list[AccountingAuditCandidateFinding]:
        sentences = self._sentences(text)
        findings: list[AccountingAuditCandidateFinding] = []

        findings.extend(
            self._keyword_findings(
                sentences=sentences,
                category=AccountingAuditCategory.DOCUMENTARY_GAP,
                title="Documentary gap is documented",
                description=(
                    "The document states that required support, evidence, invoice, "
                    "contract, or accounting rationale is missing."
                ),
                severity=AccountingAuditSeverity.HIGH,
                required_any=(
                    "missing",
                    "without",
                    "no ",
                    "not provided",
                    "not documented",
                    "sem",
                    "ausência",
                    "ausencia",
                    "não documentado",
                    "nao documentado",
                ),
                required_terms=(
                    "support",
                    "evidence",
                    "invoice",
                    "contract",
                    "documentation",
                    "rationale",
                    "suporte",
                    "evidência",
                    "evidencia",
                    "nota fiscal",
                    "contrato",
                    "documentação",
                    "documentacao",
                ),
            )
        )
        findings.extend(
            self._keyword_findings(
                sentences=sentences,
                category=AccountingAuditCategory.CONTROL_GAP,
                title="Control gap is documented",
                description=(
                    "The document states that a control, review, validation, or check "
                    "is missing or was not performed."
                ),
                severity=AccountingAuditSeverity.HIGH,
                required_any=(
                    "missing",
                    "without",
                    "no ",
                    "not performed",
                    "not reviewed",
                    "sem",
                    "não",
                    "nao",
                ),
                required_terms=(
                    "control",
                    "review",
                    "validation",
                    "check",
                    "controle",
                    "revisão",
                    "revisao",
                    "validação",
                    "validacao",
                ),
            )
        )
        findings.extend(
            self._keyword_findings(
                sentences=sentences,
                category=AccountingAuditCategory.TRACEABILITY_GAP,
                title="Traceability gap is documented",
                description=(
                    "The document indicates missing traceability or inability to link "
                    "the transaction to source records."
                ),
                severity=AccountingAuditSeverity.HIGH,
                required_any=(
                    "not traceable",
                    "cannot trace",
                    "cannot link",
                    "no audit trail",
                    "traceability gap",
                    "sem rastreabilidade",
                    "não rastreável",
                    "nao rastreavel",
                ),
                required_terms=(),
            )
        )
        findings.extend(
            self._keyword_findings(
                sentences=sentences,
                category=AccountingAuditCategory.RECONCILIATION_GAP,
                title="Reconciliation gap is documented",
                description=(
                    "The document states that reconciliation is missing, incomplete, "
                    "or not performed."
                ),
                severity=AccountingAuditSeverity.HIGH,
                required_any=(
                    "not reconciled",
                    "unreconciled",
                    "reconciliation not performed",
                    "without reconciliation",
                    "no reconciliation",
                    "sem conciliação",
                    "sem conciliacao",
                    "não conciliado",
                    "nao conciliado",
                ),
                required_terms=(),
            )
        )
        findings.extend(self._cost_center_findings(sentences))
        findings.extend(self._approval_weakness_findings(sentences))
        findings.extend(self._posting_inconsistency_findings(sentences))

        return self._dedupe_findings(findings)

    def _cost_center_findings(
        self,
        sentences: list[str],
    ) -> list[AccountingAuditCandidateFinding]:
        findings: list[AccountingAuditCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if "cost center" not in lower_sentence and "centro de custo" not in lower_sentence:
                continue
            if not any(
                term in lower_sentence
                for term in (
                    "wrong",
                    "incorrect",
                    "mismatch",
                    "inconsistent",
                    "does not match",
                    "different from",
                    "errado",
                    "incorreto",
                    "diverg",
                    "inconsistente",
                )
            ):
                continue
            findings.append(
                self._finding(
                    category=AccountingAuditCategory.COST_CENTER_INCONSISTENCY,
                    title="Cost center inconsistency is documented",
                    description=(
                        "The document indicates the cost center is inconsistent, "
                        "incorrect, or does not match the described allocation."
                    ),
                    severity=AccountingAuditSeverity.MEDIUM,
                    evidence=[sentence],
                    cost_center_references=self._cost_centers(sentence),
                )
            )
        return findings

    def _approval_weakness_findings(
        self,
        sentences: list[str],
    ) -> list[AccountingAuditCandidateFinding]:
        findings: list[AccountingAuditCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(
                term in lower_sentence
                for term in (
                    "approval",
                    "approved",
                    "approver",
                    "aprovação",
                    "aprovacao",
                    "aprovado",
                    "aprovador",
                )
            ):
                continue
            if not any(
                term in lower_sentence
                for term in (
                    "missing",
                    "without",
                    "no ",
                    "informal",
                    "verbal",
                    "whatsapp",
                    "after payment",
                    "sem",
                    "informal",
                    "verbal",
                    "após o pagamento",
                    "apos o pagamento",
                )
            ):
                continue
            findings.append(
                self._finding(
                    category=AccountingAuditCategory.APPROVAL_WEAKNESS,
                    title="Approval weakness is documented",
                    description=(
                        "The document indicates approval is missing, informal, late, "
                        "or otherwise weak."
                    ),
                    severity=AccountingAuditSeverity.MEDIUM,
                    evidence=[sentence],
                )
            )
        return findings

    def _posting_inconsistency_findings(
        self,
        sentences: list[str],
    ) -> list[AccountingAuditCandidateFinding]:
        findings: list[AccountingAuditCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(
                term in lower_sentence
                for term in (
                    "posting",
                    "debit",
                    "credit",
                    "journal entry",
                    "account",
                    "lançamento",
                    "lancamento",
                    "débito",
                    "debito",
                    "crédito",
                    "credito",
                    "conta",
                )
            ):
                continue
            if not any(
                term in lower_sentence
                for term in (
                    "wrong",
                    "incorrect",
                    "mismatch",
                    "inconsistent",
                    "does not match",
                    "unbalanced",
                    "diverg",
                    "incorreto",
                    "errado",
                    "inconsistente",
                    "não fecha",
                    "nao fecha",
                )
            ):
                continue
            findings.append(
                self._finding(
                    category=AccountingAuditCategory.POSTING_INCONSISTENCY,
                    title="Posting inconsistency is documented",
                    description=(
                        "The document indicates an inconsistency in account usage, "
                        "debit/credit posting, or journal-entry logic."
                    ),
                    severity=AccountingAuditSeverity.HIGH,
                    evidence=[sentence],
                    account_references=self._accounts(sentence),
                )
            )
        return findings

    def _keyword_findings(
        self,
        sentences: list[str],
        category: AccountingAuditCategory,
        title: str,
        description: str,
        severity: AccountingAuditSeverity,
        required_any: tuple[str, ...],
        required_terms: tuple[str, ...],
    ) -> list[AccountingAuditCandidateFinding]:
        findings: list[AccountingAuditCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if required_any and not any(term in lower_sentence for term in required_any):
                continue
            if required_terms and not any(term in lower_sentence for term in required_terms):
                continue
            findings.append(
                self._finding(
                    category=category,
                    title=title,
                    description=description,
                    severity=severity,
                    evidence=[sentence],
                )
            )
        return findings

    def _finding(
        self,
        category: AccountingAuditCategory,
        title: str,
        description: str,
        severity: AccountingAuditSeverity,
        evidence: list[str],
        account_references: list[str] | None = None,
        cost_center_references: list[str] | None = None,
    ) -> AccountingAuditCandidateFinding:
        evidence_key = self._slug(evidence[0])[:32]
        return AccountingAuditCandidateFinding(
            id=f"{category.value}-{evidence_key}",
            category=category,
            title=title,
            description=description,
            severity=severity,
            evidence=[
                AccountingAuditEvidence(text=evidence_text)
                for evidence_text in evidence
                if evidence_text
            ],
            account_references=account_references or [],
            cost_center_references=cost_center_references or [],
        )

    def _validate_output_references(
        self,
        output: AccountingAuditAgentOutput,
        document_text: str,
    ) -> None:
        for finding in output.findings:
            for evidence in finding.evidence:
                if evidence.source != "document" or evidence.text not in document_text:
                    raise ValueError(
                        "accounting audit evidence must come from document content"
                    )
            for account in finding.account_references:
                if account not in document_text:
                    raise ValueError(
                        "accounting audit account references must come from document content"
                    )
            for cost_center in finding.cost_center_references:
                if cost_center not in document_text:
                    raise ValueError(
                        "accounting audit cost center references must come from document content"
                    )

    def _dedupe_findings(
        self,
        findings: list[AccountingAuditCandidateFinding],
    ) -> list[AccountingAuditCandidateFinding]:
        deduped: list[AccountingAuditCandidateFinding] = []
        seen: set[tuple[AccountingAuditCategory, str]] = set()
        for finding in findings:
            key = (finding.category, finding.evidence[0].text)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _accounts(self, sentence: str) -> list[str]:
        return [
            self._clean_reference(match.group("value"))
            for match in re.finditer(
                r"\b(?:account|conta)\s+(?:code\s+)?"
                r"(?P<value>\d[\d.-]*(?:\s+-\s+[A-Za-zÀ-ÿ ]{2,40}?)?)"
                r"(?=\s+(?:is|was|does|do|but|however)\b|[.,;:]|$)",
                sentence,
                flags=re.IGNORECASE,
            )
            if self._clean_reference(match.group("value"))
        ]

    def _cost_centers(self, sentence: str) -> list[str]:
        return [
            self._clean_reference(match.group("value"))
            for match in re.finditer(
                r"\b(?:cost center|centro de custo)\s+"
                r"(?P<value>[A-Z]{1,6}-?\d{1,8}(?:\s+[A-Za-zÀ-ÿ]+)?)",
                sentence,
                flags=re.IGNORECASE,
            )
            if self._clean_reference(match.group("value"))
        ]

    def _sentences(self, text: str) -> list[str]:
        candidates: list[str] = []
        for line in text.splitlines():
            cleaned_line = re.sub(r"^\s*[-*•\d.)]+\s*", "", line).strip()
            if not cleaned_line:
                continue
            candidates.extend(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?;:])\s+", cleaned_line)
                if sentence.strip()
            )
        return candidates

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "evidence"

    def _clean_reference(self, value: str) -> str:
        return " ".join(value.strip(" .,:;").split())

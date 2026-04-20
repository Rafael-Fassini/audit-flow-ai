import json
import re
from datetime import date, datetime
from typing import Protocol

from pydantic import ValidationError

from app.agents.prompts.base import PromptPayload
from app.agents.prompts.red_flag import build_red_flag_prompt
from app.models.document import DocumentMetadata
from app.models.document_section import ParsedDocument
from app.schemas.agents import (
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    DocumentUnderstandingResult,
    RedFlagAgentOutput,
    RedFlagCandidateFinding,
    RedFlagEvidence,
    RedFlagSeverity,
    RedFlagType,
)


class RedFlagModelProvider(Protocol):
    def generate(self, prompt: PromptPayload) -> dict | str:
        raise NotImplementedError


class RedFlagAgent:
    def __init__(self, model_provider: RedFlagModelProvider | None = None) -> None:
        self._model_provider = model_provider

    def detect(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
        understanding: DocumentUnderstandingResult | None = None,
        analysis_id: str | None = None,
    ) -> RedFlagAgentOutput:
        prompt = build_red_flag_prompt(
            parsed_document=parsed_document,
            document_metadata=document_metadata,
            understanding=understanding,
        )
        if self._model_provider is not None:
            try:
                provider_output = self._model_provider.generate(prompt)
                if isinstance(provider_output, str):
                    provider_output = json.loads(provider_output)
                output = RedFlagAgentOutput.model_validate(provider_output)
                self._validate_evidence_is_from_document(output, parsed_document.text)
                return output
            except (TypeError, ValueError, ValidationError, json.JSONDecodeError):
                return RedFlagAgentOutput(
                    metadata=self._metadata(
                        document_metadata=document_metadata,
                        analysis_id=analysis_id,
                        status=AgentOutputStatus.NEEDS_REVIEW,
                        errors=[
                            AgentError(
                                code="invalid_red_flag_model_output",
                                message=(
                                    "Red flag model output did not validate or cited "
                                    "unsupported evidence; deterministic fallback was used."
                                ),
                                retryable=True,
                            )
                        ],
                    ),
                    findings=self._fallback_findings(parsed_document.text),
                )

        return RedFlagAgentOutput(
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
            agent_role=AgentRole.RED_FLAG,
            status=status,
            analysis_id=analysis_id,
            document_id=document_metadata.id,
            source_filename=document_metadata.original_filename,
            errors=errors or [],
        )

    def _fallback_findings(self, text: str) -> list[RedFlagCandidateFinding]:
        sentences = self._sentences(text)
        findings: list[RedFlagCandidateFinding] = []

        findings.extend(self._impossible_date_findings(text))
        findings.extend(self._conflicting_value_findings(sentences))
        findings.extend(self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.MISSING_PROCUREMENT_ARTIFACTS,
            title="Missing procurement artifact is documented",
            description=(
                "The document states that a purchase order, contract, quote, or "
                "equivalent procurement support is missing."
            ),
            severity=RedFlagSeverity.HIGH,
            required_any=("missing", "without", "no ", "not provided", "não", "nao", "sem"),
            required_terms=("purchase order", "po", "contract", "quote", "procurement", "pedido de compra", "contrato", "cotação", "cotacao"),
        ))
        findings.extend(self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.INFORMAL_APPROVAL,
            title="Informal approval channel is documented",
            description=(
                "The document indicates approval through an informal channel such as "
                "messaging, chat, or verbal approval."
            ),
            severity=RedFlagSeverity.MEDIUM,
            required_any=("approval", "approved", "approve", "aprovação", "aprovacao", "aprovado", "aprova"),
            required_terms=("whatsapp", "message", "chat", "verbal", "sms", "telegram", "mensagem"),
        ))
        findings.extend(self._payment_before_invoice_findings(sentences))
        findings.extend(self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.PAYMENT_TO_PERSONAL_OR_THIRD_PARTY_ACCOUNT,
            title="Payment to personal or third-party account is documented",
            description=(
                "The document states that payment was made or instructed to a personal, "
                "third-party, or non-registered account."
            ),
            severity=RedFlagSeverity.HIGH,
            required_any=("payment", "paid", "transfer", "wire", "pix", "pagamento", "pago", "transferência", "transferencia"),
            required_terms=("personal account", "third-party account", "third party account", "individual account", "not registered", "unregistered", "conta de terceiro", "conta pessoal", "pessoa física", "pessoa fisica"),
        ))
        findings.extend(self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.INFORMAL_PAYMENT_INSTRUCTIONS,
            title="Informal payment instructions are documented",
            description=(
                "The document indicates payment instructions or bank details were sent "
                "through an informal messaging channel."
            ),
            severity=RedFlagSeverity.HIGH,
            required_any=("payment instruction", "payment details", "bank details", "pix", "wire instruction", "instrução de pagamento", "instrucao de pagamento", "dados bancários", "dados bancarios"),
            required_terms=("whatsapp", "message", "chat", "sms", "telegram", "mensagem"),
        ))
        findings.extend(self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.URGENCY_OVERRIDE_WITHOUT_SUPPORT,
            title="Urgency override without support is documented",
            description=(
                "The document describes an urgent override, exception, or bypass without "
                "supporting evidence."
            ),
            severity=RedFlagSeverity.HIGH,
            required_any=("urgent", "urgency", "immediate", "exception", "override", "bypass", "urgente", "exceção", "excecao"),
            required_terms=("without support", "no support", "no evidence", "without evidence", "sem suporte", "sem evidência", "sem evidencia"),
        ))

        return self._dedupe_findings(findings)

    def _impossible_date_findings(self, text: str) -> list[RedFlagCandidateFinding]:
        findings: list[RedFlagCandidateFinding] = []
        for value in self._date_candidates(text):
            if self._parse_date(value) is not None:
                continue
            evidence = self._sentence_containing(text, value)
            findings.append(self._finding(
                red_flag_type=RedFlagType.IMPOSSIBLE_DATE,
                title="Impossible date is documented",
                description=f"The document contains an impossible calendar date: {value}.",
                severity=RedFlagSeverity.HIGH,
                evidence=[evidence],
            ))
        return findings

    def _conflicting_value_findings(
        self,
        sentences: list[str],
    ) -> list[RedFlagCandidateFinding]:
        findings: list[RedFlagCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            values = self._money_values(sentence)
            if len(set(values)) < 2:
                continue
            if not any(term in lower_sentence for term in ("but", "however", "conflict", "mismatch", "differs", "diverge", "diverg", "mas", "porém", "porem")):
                continue
            findings.append(self._finding(
                red_flag_type=RedFlagType.CONFLICTING_VALUES,
                title="Conflicting values are documented",
                description="The same evidence sentence contains conflicting monetary values.",
                severity=RedFlagSeverity.HIGH,
                evidence=[sentence],
            ))
        return findings

    def _payment_before_invoice_findings(
        self,
        sentences: list[str],
    ) -> list[RedFlagCandidateFinding]:
        findings = self._keyword_finding(
            sentences=sentences,
            red_flag_type=RedFlagType.PAYMENT_BEFORE_INVOICE,
            title="Payment before invoice is documented",
            description="The document states that payment occurred before the invoice.",
            severity=RedFlagSeverity.HIGH,
            required_any=("payment before invoice", "paid before invoice", "pagamento antes da nota", "pago antes da nota"),
            required_terms=(),
        )
        if findings:
            return findings

        invoice_dates = self._dated_sentences(sentences, ("invoice", "nota fiscal"))
        payment_dates = self._dated_sentences(sentences, ("payment", "paid", "pagamento", "pago"))
        for payment_date, payment_sentence in payment_dates:
            for invoice_date, invoice_sentence in invoice_dates:
                if payment_date < invoice_date:
                    return [
                        self._finding(
                            red_flag_type=RedFlagType.PAYMENT_BEFORE_INVOICE,
                            title="Payment date precedes invoice date",
                            description=(
                                "The document provides a payment date earlier than the "
                                "invoice date."
                            ),
                            severity=RedFlagSeverity.HIGH,
                            evidence=[payment_sentence, invoice_sentence],
                        )
                    ]
        return []

    def _keyword_finding(
        self,
        sentences: list[str],
        red_flag_type: RedFlagType,
        title: str,
        description: str,
        severity: RedFlagSeverity,
        required_any: tuple[str, ...],
        required_terms: tuple[str, ...],
    ) -> list[RedFlagCandidateFinding]:
        findings: list[RedFlagCandidateFinding] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if required_any and not any(term in lower_sentence for term in required_any):
                continue
            if required_terms and not any(term in lower_sentence for term in required_terms):
                continue
            findings.append(self._finding(
                red_flag_type=red_flag_type,
                title=title,
                description=description,
                severity=severity,
                evidence=[sentence],
            ))
        return findings

    def _finding(
        self,
        red_flag_type: RedFlagType,
        title: str,
        description: str,
        severity: RedFlagSeverity,
        evidence: list[str],
    ) -> RedFlagCandidateFinding:
        normalized_type = red_flag_type.value
        evidence_key = self._slug(evidence[0])[:32]
        return RedFlagCandidateFinding(
            id=f"{normalized_type}-{evidence_key}",
            red_flag_type=red_flag_type,
            title=title,
            description=description,
            severity=severity,
            evidence=[
                RedFlagEvidence(text=evidence_text)
                for evidence_text in evidence
                if evidence_text
            ],
        )

    def _validate_evidence_is_from_document(
        self,
        output: RedFlagAgentOutput,
        document_text: str,
    ) -> None:
        for finding in output.findings:
            for evidence in finding.evidence:
                if evidence.source != "document" or evidence.text not in document_text:
                    raise ValueError("red flag evidence must come from document content")

    def _dedupe_findings(
        self,
        findings: list[RedFlagCandidateFinding],
    ) -> list[RedFlagCandidateFinding]:
        deduped: list[RedFlagCandidateFinding] = []
        seen: set[tuple[RedFlagType, str]] = set()
        for finding in findings:
            key = (finding.red_flag_type, finding.evidence[0].text)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

    def _dated_sentences(
        self,
        sentences: list[str],
        terms: tuple[str, ...],
    ) -> list[tuple[date, str]]:
        dated: list[tuple[date, str]] = []
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(term in lower_sentence for term in terms):
                continue
            for value in self._date_candidates(sentence):
                parsed_date = self._parse_date(value)
                if parsed_date is not None:
                    dated.append((parsed_date, sentence))
        return dated

    def _date_candidates(self, text: str) -> list[str]:
        return re.findall(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)

    def _parse_date(self, value: str) -> date | None:
        for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
            try:
                return (
                    date.fromisoformat(value)
                    if pattern == "%Y-%m-%d"
                    else datetime.strptime(value, pattern).date()
                )
            except ValueError:
                continue
        return None

    def _money_values(self, text: str) -> list[str]:
        return [
            match.group(0).strip(" .,:;")
            for match in re.finditer(
                r"(?:R\$\s?\d[\d.,]*|USD\s?\d[\d.,]*|\$\s?\d[\d.,]*|\b\d[\d.,]*\s?(?:BRL|USD|EUR)\b)",
                text,
                flags=re.IGNORECASE,
            )
        ]

    def _sentence_containing(self, text: str, value: str) -> str:
        for sentence in self._sentences(text):
            if value in sentence:
                return sentence
        return value

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

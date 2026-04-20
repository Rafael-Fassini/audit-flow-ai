import json
import re
from collections.abc import Iterable
from typing import Protocol

from pydantic import ValidationError

from app.agents.prompts.document_understanding import (
    build_document_understanding_prompt,
)
from app.agents.prompts.base import PromptPayload
from app.models.document import DocumentMetadata
from app.models.document_section import ParsedDocument
from app.schemas.agents import (
    AgentError,
    AgentOutputMetadata,
    AgentOutputStatus,
    AgentRole,
    DocumentUnderstandingAgentOutput,
    DocumentUnderstandingEntity,
    DocumentUnderstandingResult,
    DocumentUnderstandingStep,
)


class DocumentUnderstandingModelProvider(Protocol):
    def generate(self, prompt: PromptPayload) -> dict | str:
        raise NotImplementedError


class DocumentUnderstandingAgent:
    def __init__(
        self,
        model_provider: DocumentUnderstandingModelProvider | None = None,
    ) -> None:
        self._model_provider = model_provider

    def understand(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
        analysis_id: str | None = None,
    ) -> DocumentUnderstandingAgentOutput:
        metadata = self._metadata(
            document_metadata=document_metadata,
            analysis_id=analysis_id,
            status=AgentOutputStatus.COMPLETED,
        )
        prompt = build_document_understanding_prompt(parsed_document, document_metadata)

        if self._model_provider is not None:
            try:
                provider_output = self._model_provider.generate(prompt)
                if isinstance(provider_output, str):
                    provider_output = json.loads(provider_output)
                return DocumentUnderstandingAgentOutput.model_validate(
                    provider_output
                )
            except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
                return self._fallback_output(
                    parsed_document=parsed_document,
                    document_metadata=document_metadata,
                    analysis_id=analysis_id,
                    error=AgentError(
                        code="invalid_model_output",
                        message=(
                            "Document understanding model output did not validate; "
                            "deterministic fallback was used."
                        ),
                        retryable=True,
                    ),
                )

        return DocumentUnderstandingAgentOutput(
            metadata=metadata,
            understanding=self._fallback_understanding(parsed_document, document_metadata),
        )

    def _fallback_output(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
        analysis_id: str | None,
        error: AgentError,
    ) -> DocumentUnderstandingAgentOutput:
        return DocumentUnderstandingAgentOutput(
            metadata=self._metadata(
                document_metadata=document_metadata,
                analysis_id=analysis_id,
                status=AgentOutputStatus.NEEDS_REVIEW,
                errors=[error],
            ),
            understanding=self._fallback_understanding(parsed_document, document_metadata),
        )

    def _metadata(
        self,
        document_metadata: DocumentMetadata,
        analysis_id: str | None,
        status: AgentOutputStatus,
        errors: list[AgentError] | None = None,
    ) -> AgentOutputMetadata:
        return AgentOutputMetadata(
            agent_role=AgentRole.DOCUMENT_UNDERSTANDING,
            status=status,
            analysis_id=analysis_id,
            document_id=document_metadata.id,
            source_filename=document_metadata.original_filename,
            errors=errors or [],
        )

    def _fallback_understanding(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
    ) -> DocumentUnderstandingResult:
        text = parsed_document.text
        sentences = self._sentences(text)
        steps = self._extract_steps(sentences)
        controls = self._entities_from_keywords(
            sentences,
            ("control", "review", "approve", "approval", "reconcile", "controle", "revis", "aprova", "concilia"),
        )
        approvals = self._entities_from_keywords(
            sentences,
            ("approve", "approval", "approved", "manager", "aprova", "aprovação", "aprovacao"),
        )
        payments = self._entities_from_keywords(
            sentences,
            ("payment", "paid", "invoice", "cash disbursement", "pagamento", "pagar", "nota fiscal"),
        )
        account_references = self._extract_pattern_entities(
            text,
            re.compile(
                r"\b(?:account|conta)\s+(?:code\s+)?(?P<value>[A-Za-zÀ-ÿ0-9 ._-]{2,80})",
                flags=re.IGNORECASE,
            ),
        )
        cost_center_references = self._extract_pattern_entities(
            text,
            re.compile(
                r"\b(?:cost center|centro de custo)\s+"
                r"(?P<value>[A-Z]{1,6}-?\d{1,8}(?:\s+[A-Za-zÀ-ÿ]+)?)",
                flags=re.IGNORECASE,
            ),
        )

        return DocumentUnderstandingResult(
            process_name=self._infer_process_name(parsed_document, document_metadata),
            summary=self._summary(sentences, text),
            steps=steps,
            controls=controls,
            actors=self._extract_actors(text),
            values=self._extract_values(text),
            dates=self._extract_dates(text),
            approvals=approvals,
            payments=payments,
            account_references=account_references,
            cost_center_references=cost_center_references,
        )

    def _infer_process_name(
        self,
        parsed_document: ParsedDocument,
        document_metadata: DocumentMetadata,
    ) -> str:
        for line in parsed_document.text.splitlines()[:8]:
            candidate = " ".join(line.strip().split())
            if candidate and 2 <= len(candidate.split()) <= 12 and not candidate.endswith("."):
                return candidate[:120]
        return document_metadata.original_filename.rsplit(".", 1)[0].replace("_", " ").title()

    def _summary(self, sentences: list[str], text: str) -> str:
        if sentences:
            return sentences[0][:300]
        return text[:300]

    def _extract_steps(self, sentences: list[str]) -> list[DocumentUnderstandingStep]:
        keywords = (
            "receive",
            "record",
            "post",
            "approve",
            "review",
            "pay",
            "reconcile",
            "recebe",
            "registra",
            "contabiliza",
            "aprova",
            "revisa",
            "paga",
            "concilia",
        )
        steps: list[DocumentUnderstandingStep] = []
        seen: set[str] = set()
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(keyword in lower_sentence for keyword in keywords):
                continue
            key = self._semantic_key(sentence)
            if key in seen:
                continue
            seen.add(key)
            steps.append(
                DocumentUnderstandingStep(
                    index=len(steps),
                    description=sentence,
                    evidence_text=sentence,
                )
            )
        return steps

    def _entities_from_keywords(
        self,
        sentences: list[str],
        keywords: tuple[str, ...],
    ) -> list[DocumentUnderstandingEntity]:
        entities: list[DocumentUnderstandingEntity] = []
        seen: set[str] = set()
        for sentence in sentences:
            lower_sentence = sentence.lower()
            if not any(keyword in lower_sentence for keyword in keywords):
                continue
            key = self._semantic_key(sentence)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                DocumentUnderstandingEntity(value=sentence, evidence_text=sentence)
            )
        return entities

    def _extract_actors(self, text: str) -> list[DocumentUnderstandingEntity]:
        pattern = re.compile(
            r"\b(accounting team|finance team|controller|manager|approver|reviewer|"
            r"accounts payable|accounts receivable|contabilidade|financeiro|gestor|"
            r"aprovador|revisor|tesouraria|backoffice|back office)\b",
            flags=re.IGNORECASE,
        )
        return self._unique_entities(
            DocumentUnderstandingEntity(
                value=self._normalize_label(match.group(0)),
                evidence_text=match.group(0),
            )
            for match in pattern.finditer(text)
        )

    def _extract_values(self, text: str) -> list[DocumentUnderstandingEntity]:
        pattern = re.compile(
            r"(?:R\$\s?\d[\d.,]*|USD\s?\d[\d.,]*|\$\s?\d[\d.,]*|\b\d[\d.,]*\s?(?:BRL|USD|EUR)\b)",
            flags=re.IGNORECASE,
        )
        return self._unique_entities(
            DocumentUnderstandingEntity(
                value=match.group(0).strip(" .,:;"),
                evidence_text=match.group(0).strip(" .,:;"),
            )
            for match in pattern.finditer(text)
        )

    def _extract_dates(self, text: str) -> list[DocumentUnderstandingEntity]:
        pattern = re.compile(
            r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
            flags=re.IGNORECASE,
        )
        return self._unique_entities(
            DocumentUnderstandingEntity(
                value=match.group(0).strip(),
                evidence_text=match.group(0).strip(),
            )
            for match in pattern.finditer(text)
        )

    def _extract_pattern_entities(
        self,
        text: str,
        pattern: re.Pattern[str],
    ) -> list[DocumentUnderstandingEntity]:
        return self._unique_entities(
            DocumentUnderstandingEntity(
                value=self._clean_reference(match.group("value")),
                evidence_text=match.group(0).strip(),
            )
            for match in pattern.finditer(text)
            if self._clean_reference(match.group("value"))
        )

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

    def _unique_entities(
        self,
        entities: Iterable[DocumentUnderstandingEntity],
    ) -> list[DocumentUnderstandingEntity]:
        deduped: list[DocumentUnderstandingEntity] = []
        seen: set[str] = set()
        for entity in entities:
            key = self._semantic_key(entity.value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    def _semantic_key(self, value: str) -> str:
        return " ".join(value.lower().split())

    def _normalize_label(self, value: str) -> str:
        return " ".join(value.strip().split()).title()

    def _clean_reference(self, value: str) -> str:
        return " ".join(value.strip(" .,:;").split())

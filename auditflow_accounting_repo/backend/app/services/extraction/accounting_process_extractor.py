import re

from app.models.accounting_process import (
    AccountReference,
    AccountReferenceRole,
    AccountingProcess,
    ChartOfAccountsReference,
    ControlSignal,
    EvidenceSnippet,
    NarrativeGap,
    ProcessStep,
    ProcessStepType,
)
from app.models.document_section import ChunkedDocument, DocumentChunk


ACCOUNT_PATTERN = re.compile(
    r"(?P<role>debit|credit|debited|credited|dr\.?|cr\.?)?\s*"
    r"(?P<code>\b\d{3,8}(?:[-.]\d{1,4})?\b)?\s*"
    r"(?P<name>\b(?:cash|revenue|expense|accrued liabilities|liabilit(?:y|ies)|"
    r"asset|accounts payable|accounts receivable|clearing|suspense|transitional)"
    r"\b(?: account)?)",
    flags=re.IGNORECASE,
)

ACTOR_PATTERN = re.compile(
    r"\b(accounting team|finance team|controller|manager|reviewer|approver|"
    r"shared services|accounts payable|accounts receivable)\b",
    flags=re.IGNORECASE,
)

SYSTEM_PATTERN = re.compile(
    r"\b(ERP|SAP|Oracle|NetSuite|QuickBooks|general ledger|GL)\b",
    flags=re.IGNORECASE,
)

CONTROL_KEYWORDS = (
    "approve",
    "approval",
    "review",
    "reconcile",
    "control",
    "evidence",
    "support",
)

POSTING_KEYWORDS = ("debit", "credit", "journal entry", "posting", "post ")
GAP_KEYWORDS = ("not documented", "missing", "unclear", "without rationale", "no evidence")


class AccountingProcessExtractor:
    def extract(self, document: ChunkedDocument) -> AccountingProcess:
        steps = self._extract_steps(document.chunks)
        account_references = self._extract_account_references(document.chunks)
        chart_references = self._extract_chart_references(
            document.chunks,
            account_references,
        )
        controls = self._extract_controls(document.chunks)
        posting_logic = self._extract_posting_logic(document.chunks)
        narrative_gaps = self._extract_narrative_gaps(document.chunks)

        return AccountingProcess(
            process_name=self._infer_process_name(document),
            summary=self._build_summary(document),
            source_filename=document.filename,
            steps=steps,
            account_references=account_references,
            chart_of_accounts_references=chart_references,
            controls=controls,
            posting_logic=posting_logic,
            narrative_gaps=narrative_gaps,
        )

    def _infer_process_name(self, document: ChunkedDocument) -> str:
        for section in document.sections:
            if section.title:
                return section.title.rstrip(":")
        return "Accounting entry process"

    def _build_summary(self, document: ChunkedDocument) -> str:
        first_chunk = document.chunks[0].text if document.chunks else document.text
        first_sentence = re.split(r"(?<=[.!?])\s+", first_chunk.strip())[0]
        return first_sentence[:300] or "Structured accounting process extracted."

    def _extract_steps(self, chunks: list[DocumentChunk]) -> list[ProcessStep]:
        steps: list[ProcessStep] = []
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not self._looks_like_process_step(sentence):
                    continue
                steps.append(
                    ProcessStep(
                        index=len(steps),
                        step_type=self._classify_step(sentence),
                        description=sentence,
                        actors=self._find_actor_matches(sentence),
                        systems=self._find_system_matches(sentence),
                        evidence=self._evidence(chunk, sentence),
                    )
                )
        return steps

    def _extract_account_references(
        self,
        chunks: list[DocumentChunk],
    ) -> list[AccountReference]:
        references: list[AccountReference] = []
        seen: set[tuple[str, str | None, str]] = set()
        for chunk in chunks:
            for match in ACCOUNT_PATTERN.finditer(chunk.text):
                account_name = self._normalize_label(match.group("name"))
                account_code = match.group("code")
                role = self._normalize_role(match.group("role"))
                key = (account_name.lower(), account_code, role.value)
                if key in seen:
                    continue
                seen.add(key)
                references.append(
                    AccountReference(
                        role=role,
                        account_code=account_code,
                        account_name=account_name,
                        evidence=self._evidence(chunk, match.group(0).strip()),
                    )
                )
        return references

    def _extract_chart_references(
        self,
        chunks: list[DocumentChunk],
        accounts: list[AccountReference],
    ) -> list[ChartOfAccountsReference]:
        references: list[ChartOfAccountsReference] = []
        for chunk in chunks:
            lower_text = chunk.text.lower()
            if "chart of accounts" not in lower_text and "account classification" not in lower_text:
                continue
            related_accounts = [
                account
                for account in accounts
                if account.evidence.chunk_index == chunk.index
            ]
            references.append(
                ChartOfAccountsReference(
                    reference_text=self._first_relevant_sentence(
                        chunk.text,
                        ("chart of accounts", "account classification"),
                    ),
                    accounts=related_accounts,
                    evidence=self._evidence(chunk, chunk.text[:200]),
                )
            )
        return references

    def _extract_controls(self, chunks: list[DocumentChunk]) -> list[ControlSignal]:
        controls: list[ControlSignal] = []
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not any(keyword in sentence.lower() for keyword in CONTROL_KEYWORDS):
                    continue
                controls.append(
                    ControlSignal(
                        description=sentence,
                        owner=self._find_first_actor(sentence),
                        evidence=self._evidence(chunk, sentence),
                    )
                )
        return controls

    def _extract_posting_logic(self, chunks: list[DocumentChunk]) -> list[str]:
        posting_logic: list[str] = []
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if any(keyword in sentence.lower() for keyword in POSTING_KEYWORDS):
                    posting_logic.append(sentence)
        return posting_logic

    def _extract_narrative_gaps(self, chunks: list[DocumentChunk]) -> list[NarrativeGap]:
        gaps: list[NarrativeGap] = []
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not any(keyword in sentence.lower() for keyword in GAP_KEYWORDS):
                    continue
                gaps.append(
                    NarrativeGap(
                        description=sentence,
                        evidence=self._evidence(chunk, sentence),
                    )
                )
        return gaps

    def _looks_like_process_step(self, sentence: str) -> bool:
        lower_sentence = sentence.lower()
        keywords = (
            "receive",
            "approve",
            "review",
            "record",
            "post",
            "debit",
            "credit",
            "reconcile",
            "prepare",
        )
        return any(keyword in lower_sentence for keyword in keywords)

    def _classify_step(self, sentence: str) -> ProcessStepType:
        lower_sentence = sentence.lower()
        if "approve" in lower_sentence or "approval" in lower_sentence:
            return ProcessStepType.APPROVAL
        if any(keyword in lower_sentence for keyword in POSTING_KEYWORDS):
            return ProcessStepType.POSTING
        if "review" in lower_sentence or "reconcile" in lower_sentence:
            return ProcessStepType.REVIEW
        if "control" in lower_sentence:
            return ProcessStepType.CONTROL
        if "receive" in lower_sentence or "event" in lower_sentence:
            return ProcessStepType.EVENT
        return ProcessStepType.OTHER

    def _normalize_role(self, role: str | None) -> AccountReferenceRole:
        if role is None:
            return AccountReferenceRole.UNSPECIFIED
        normalized = role.lower().replace(".", "")
        if normalized in {"debit", "debited", "dr"}:
            return AccountReferenceRole.DEBIT
        if normalized in {"credit", "credited", "cr"}:
            return AccountReferenceRole.CREDIT
        return AccountReferenceRole.UNSPECIFIED

    def _sentences(self, text: str) -> list[str]:
        return [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ]

    def _evidence(self, chunk: DocumentChunk, text: str) -> EvidenceSnippet:
        return EvidenceSnippet(
            section_index=chunk.section_index,
            chunk_index=chunk.index,
            text=text.strip(),
        )

    def _first_relevant_sentence(self, text: str, needles: tuple[str, ...]) -> str:
        for sentence in self._sentences(text):
            if any(needle in sentence.lower() for needle in needles):
                return sentence
        return text[:200]

    def _find_actor_matches(self, text: str) -> list[str]:
        return list(
            dict.fromkeys(
                self._normalize_label(match).title()
                for match in ACTOR_PATTERN.findall(text)
            )
        )

    def _find_system_matches(self, text: str) -> list[str]:
        systems: list[str] = []
        for match in SYSTEM_PATTERN.findall(text):
            normalized = self._normalize_label(match)
            if normalized.lower() in {"erp", "sap", "gl"}:
                systems.append(normalized.upper())
            else:
                systems.append(normalized)
        return list(dict.fromkeys(systems))

    def _find_first_actor(self, text: str) -> str | None:
        matches = self._find_actor_matches(text)
        return matches[0] if matches else None

    def _normalize_label(self, value: str) -> str:
        return " ".join(value.strip().split())

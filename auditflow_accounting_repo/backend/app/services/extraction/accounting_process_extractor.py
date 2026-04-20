import re
from pathlib import Path

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
    r"shared services|accounts payable|accounts receivable|contabilidade|"
    r"financeiro|corretora|tesouraria|custodiante|terceiro|prestador|"
    r"backoffice|back office|compliance|auditoria interna)\b",
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
    "aprovação",
    "aprovacao",
    "aprovar",
    "revisão",
    "revisao",
    "revisa",
    "validar",
    "valida",
    "conciliação",
    "conciliacao",
    "controle",
    "evidência",
    "evidencia",
    "suporte",
)

POSTING_KEYWORDS = (
    "debit",
    "credit",
    "journal entry",
    "posting",
    "post ",
    "débito",
    "debito",
    "crédito",
    "credito",
    "lançamento",
    "lancamento",
    "contabiliza",
    "contabilização",
    "contabilizacao",
    "registro contábil",
    "registro contabil",
)
GAP_KEYWORDS = (
    "not documented",
    "missing",
    "unclear",
    "without rationale",
    "no evidence",
    "não documentado",
    "nao documentado",
    "ausência",
    "ausencia",
    "limitação",
    "limitacao",
    "limitações",
    "limitacoes",
    "sem evidência",
    "sem evidencia",
    "rastreabilidade",
    "dependência de terceiros",
    "dependencia de terceiros",
    "fragilidade",
    "inconsistência",
    "inconsistencia",
    "não foi identificado",
    "nao foi identificado",
)

RISK_SECTION_TITLES = (
    "riscos identificados",
    "identified risks",
    "limitações",
    "limitacoes",
    "limitations",
    "fragilidades",
    "fragilidade",
    "conclusão",
    "conclusao",
    "conclusion",
)

SECTION_ONLY_TERMS = (
    "risco",
    "riscos",
    "riscos identificados",
    "controles",
    "controles internos observados",
    "limitacoes",
    "limitações",
    "conclusao",
    "conclusão",
    "fluxo operacional",
    "objetivo",
    "escopo",
)


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
        narrative_gaps.extend(
            self._missing_structured_element_gaps(
                document=document,
                account_references=account_references,
                chart_references=chart_references,
                posting_logic=posting_logic,
            )
        )

        return AccountingProcess(
            process_name=self._infer_process_name(document, steps),
            summary=self._build_summary(document),
            source_filename=document.filename,
            steps=steps,
            account_references=account_references,
            chart_of_accounts_references=chart_references,
            controls=controls,
            posting_logic=posting_logic,
            narrative_gaps=narrative_gaps,
        )

    def _infer_process_name(
        self,
        document: ChunkedDocument,
        steps: list[ProcessStep],
    ) -> str:
        functional_name = self._functional_process_name(document, steps)
        if functional_name:
            return functional_name

        for section in document.sections:
            if section.title and self._is_functional_title(section.title):
                return self._clean_title(section.title)
        for candidate in self._candidate_title_lines(document.text):
            if self._is_functional_title(candidate):
                return self._clean_title(candidate)
        filename_title = Path(document.filename).stem.replace("_", " ").replace("-", " ")
        normalized_filename = self._normalize_label(filename_title).title()
        return normalized_filename or "Accounting entry process"

    def _build_summary(self, document: ChunkedDocument) -> str:
        first_chunk = document.chunks[0].text if document.chunks else document.text
        first_sentence = re.split(r"(?<=[.!?])\s+", first_chunk.strip())[0]
        return first_sentence[:300] or "Structured accounting process extracted."

    def _extract_steps(self, chunks: list[DocumentChunk]) -> list[ProcessStep]:
        steps: list[ProcessStep] = []
        seen: set[str] = set()
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not self._looks_like_process_step(sentence):
                    continue
                if not self._is_informative_sentence(sentence):
                    continue
                normalized = self._semantic_key(sentence)
                if normalized in seen:
                    continue
                seen.add(normalized)
                actors = self._find_actor_matches(sentence)
                systems = self._find_system_matches(sentence)
                steps.append(
                    ProcessStep(
                        index=len(steps),
                        step_type=self._classify_step(sentence),
                        description=self._normalize_step_description(
                            sentence=sentence,
                            actors=actors,
                            systems=systems,
                        ),
                        actors=actors,
                        systems=systems,
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
        seen: set[str] = set()
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not self._is_informative_sentence(sentence):
                    continue
                normalized_sentence = self._normalize_for_matching(sentence)
                if not any(keyword in normalized_sentence for keyword in CONTROL_KEYWORDS):
                    continue
                semantic_key = self._semantic_key(sentence)
                if semantic_key in seen:
                    continue
                seen.add(semantic_key)
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
        seen: set[str] = set()
        for chunk in chunks:
            for sentence in self._sentences(chunk.text):
                if not self._is_informative_sentence(sentence):
                    continue
                normalized_sentence = self._normalize_for_matching(sentence)
                if any(keyword in normalized_sentence for keyword in POSTING_KEYWORDS):
                    semantic_key = self._semantic_key(sentence)
                    if semantic_key in seen:
                        continue
                    seen.add(semantic_key)
                    posting_logic.append(sentence)
        return posting_logic

    def _extract_narrative_gaps(self, chunks: list[DocumentChunk]) -> list[NarrativeGap]:
        gaps: list[NarrativeGap] = []
        seen: set[str] = set()
        for chunk in chunks:
            section_title = chunk.title or ""
            for sentence in self._sentences(chunk.text):
                if not self._is_informative_sentence(sentence):
                    continue
                normalized_sentence = self._normalize_for_matching(sentence)
                normalized_title = self._normalize_for_matching(section_title)
                if not (
                    any(keyword in normalized_sentence for keyword in GAP_KEYWORDS)
                    or any(title in normalized_title for title in RISK_SECTION_TITLES)
                    or "risco" in normalized_sentence
                    or "risk" in normalized_sentence
                ):
                    continue
                semantic_key = self._semantic_key(sentence)
                if semantic_key in seen:
                    continue
                seen.add(semantic_key)
                gaps.append(
                    NarrativeGap(
                        description=sentence,
                        evidence=self._evidence(chunk, sentence),
                    )
                )
        return gaps

    def _looks_like_process_step(self, sentence: str) -> bool:
        if self._is_section_only_fragment(sentence):
            return False
        lower_sentence = self._normalize_for_matching(sentence)
        keywords = (
            "receive",
            "receives",
            "approve",
            "approves",
            "review",
            "reviews",
            "record",
            "records",
            "post",
            "debit",
            "credit",
            "reconcile",
            "reconciles",
            "prepare",
            "prepares",
            "recebe",
            "envia",
            "solicita",
            "aprova",
            "valida",
            "revisa",
            "registra",
            "contabiliza",
            "processa",
            "executa",
            "concilia",
            "monitora",
            "classifica",
            "apura",
        )
        return any(keyword in lower_sentence for keyword in keywords)

    def _classify_step(self, sentence: str) -> ProcessStepType:
        lower_sentence = self._normalize_for_matching(sentence)
        if any(keyword in lower_sentence for keyword in ("approve", "approval", "aprova", "aprovacao")):
            return ProcessStepType.APPROVAL
        if any(keyword in lower_sentence for keyword in POSTING_KEYWORDS):
            return ProcessStepType.POSTING
        if any(
            keyword in lower_sentence
            for keyword in ("review", "reconcile", "revis", "concilia", "valid")
        ):
            return ProcessStepType.REVIEW
        if "control" in lower_sentence or "controle" in lower_sentence:
            return ProcessStepType.CONTROL
        if "receive" in lower_sentence or "recebe" in lower_sentence or "event" in lower_sentence:
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

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = " ".join(candidate.split())
            if normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            deduped.append(normalized)
        return deduped

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

    def _normalize_step_description(
        self,
        sentence: str,
        actors: list[str],
        systems: list[str],
    ) -> str:
        description = self._normalize_label(sentence)
        description = re.sub(r"^\s*[-*•\d.)]+\s*", "", description).strip()
        if description and not description.endswith((".", "!", "?")):
            description = f"{description}."

        context_parts: list[str] = []
        if actors:
            context_parts.append(f"Responsible party: {', '.join(actors)}")
        if systems:
            context_parts.append(f"System: {', '.join(systems)}")

        if context_parts:
            return f"{description} {'; '.join(context_parts)}."
        return description

    def _missing_structured_element_gaps(
        self,
        document: ChunkedDocument,
        account_references: list[AccountReference],
        chart_references: list[ChartOfAccountsReference],
        posting_logic: list[str],
    ) -> list[NarrativeGap]:
        evidence = self._fallback_evidence(document)
        gaps: list[NarrativeGap] = []
        if not account_references:
            gaps.append(
                NarrativeGap(
                    description=(
                        "Account references were not identified in the document."
                    ),
                    evidence=evidence,
                )
            )
        if not chart_references:
            gaps.append(
                NarrativeGap(
                    description=(
                        "Chart-of-accounts references were not identified in the document."
                    ),
                    evidence=evidence,
                )
            )
        if not posting_logic:
            gaps.append(
                NarrativeGap(
                    description="Posting logic was not identified in the document.",
                    evidence=evidence,
                )
            )
        return gaps

    def _fallback_evidence(self, document: ChunkedDocument) -> EvidenceSnippet:
        if document.chunks:
            chunk = document.chunks[0]
            return self._evidence(chunk, chunk.text[:240])
        return EvidenceSnippet(section_index=0, chunk_index=0, text=document.text[:240])

    def _candidate_title_lines(self, text: str) -> list[str]:
        candidates: list[str] = []
        for line in text.splitlines()[:8]:
            candidate = self._normalize_label(line)
            if not candidate or len(candidate) > 120 or candidate.endswith("."):
                continue
            candidates.append(candidate)
        return candidates

    def _is_supporting_section_title(self, title: str) -> bool:
        normalized = self._normalize_for_matching(title)
        supporting_titles = (
            "riscos identificados",
            "controles internos observados",
            "controles observados",
            "limitacoes",
            "conclusao",
            "identified risks",
            "internal controls observed",
            "limitations",
            "conclusion",
        )
        return any(value in normalized for value in supporting_titles)

    def _is_functional_title(self, title: str) -> bool:
        return (
            not self._is_supporting_section_title(title)
            and not self._is_section_only_fragment(title)
            and len(self._tokens(title)) >= 2
        )

    def _clean_title(self, title: str) -> str:
        cleaned = self._normalize_label(title.rstrip(":"))
        lowered = self._normalize_for_matching(cleaned)
        prefixes = (
            "memorando de ",
            "memorando ",
            "walkthrough de ",
            "walkthrough ",
        )
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        return cleaned[:120] or title

    def _functional_process_name(
        self,
        document: ChunkedDocument,
        steps: list[ProcessStep],
    ) -> str | None:
        combined_text = self._normalize_for_matching(
            " ".join(
                [
                    document.filename,
                    document.text[:1200],
                    " ".join(step.description for step in steps[:5]),
                ]
            )
        )
        if "corretora" in combined_text:
            if any(
                term in combined_text
                for term in ("fechamento", "contabil", "contabilidade", "lancamento")
            ):
                return "Processo operacional e contábil de corretora"
            return "Processo operacional de corretora"
        if "tesouraria" in combined_text:
            return "Processo operacional de tesouraria"
        return None

    def _is_informative_sentence(self, sentence: str) -> bool:
        tokens = self._tokens(sentence)
        if len(tokens) < 5:
            return False
        if self._is_section_only_fragment(sentence):
            return False
        return True

    def _is_section_only_fragment(self, value: str) -> bool:
        normalized = self._normalize_for_matching(value).strip(" .:-")
        return normalized in SECTION_ONLY_TERMS

    def _tokens(self, value: str) -> list[str]:
        return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", value)

    def _semantic_key(self, value: str) -> str:
        normalized = self._normalize_for_matching(value)
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if token
            not in {
                "a",
                "o",
                "os",
                "as",
                "de",
                "do",
                "da",
                "dos",
                "das",
                "e",
                "para",
                "com",
                "the",
                "and",
                "of",
                "to",
            }
        ]
        return " ".join(tokens[:14])

    def _normalize_for_matching(self, value: str) -> str:
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
        return normalized

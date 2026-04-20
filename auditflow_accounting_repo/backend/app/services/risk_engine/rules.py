from app.models.accounting_process import AccountReferenceRole, AccountingProcess
from app.models.risk import (
    FindingSource,
    FindingSeverity,
    FindingEvidence,
    Inconsistency,
    InconsistencyType,
    RiskCategory,
    RiskInferenceResult,
    RiskItem,
    evidence_from_process,
)


GENERIC_ACCOUNT_TERMS = ("clearing", "suspense", "transitional", "generic")
SUPPORT_TERMS = ("support", "evidence", "document", "invoice", "memo", "rationale")
CONTROL_TERMS = ("approve", "approval", "review", "reconcile", "control")

TRACEABILITY_TERMS = ("traceability", "rastreabilidade", "trilha de auditoria")
THIRD_PARTY_TERMS = (
    "third party",
    "third-party",
    "terceiro",
    "terceiros",
    "corretora",
    "custodiante",
    "prestador",
)
OPERATIONAL_INCONSISTENCY_TERMS = (
    "inconsistency",
    "inconsistência",
    "inconsistencia",
    "divergência",
    "divergencia",
    "manual",
    "reprocessamento",
)
CONTROL_WEAKNESS_TERMS = (
    "weak control",
    "fragilidade",
    "limitação",
    "limitacao",
    "limitações",
    "limitacoes",
    "sem evidência",
    "sem evidencia",
    "não documentado",
    "nao documentado",
)


class AccountingRiskRules:
    def evaluate(self, process: AccountingProcess) -> RiskInferenceResult:
        inconsistencies: list[Inconsistency] = []
        inconsistencies.extend(self._generic_account_findings(process))
        inconsistencies.extend(self._missing_debit_or_credit_findings(process))
        inconsistencies.extend(self._missing_support_findings(process))
        inconsistencies.extend(self._missing_control_findings(process))
        inconsistencies.extend(self._narrative_gap_findings(process))
        inconsistencies = self._dedupe_inconsistencies(inconsistencies)

        risks = self._risks_from_inconsistencies(inconsistencies)
        risks = self._dedupe_risks(risks)
        return RiskInferenceResult(inconsistencies=inconsistencies, risks=risks)

    def _generic_account_findings(
        self,
        process: AccountingProcess,
    ) -> list[Inconsistency]:
        findings: list[Inconsistency] = []
        for account in process.account_references:
            if not any(
                term in account.account_name.lower()
                for term in GENERIC_ACCOUNT_TERMS
            ):
                continue
            finding_id = f"heuristic-generic-account-{len(findings)}"
            findings.append(
                Inconsistency(
                    id=finding_id,
                    type=InconsistencyType.ACCOUNT_USAGE,
                    title="Generic or transitional account usage needs rationale",
                    description=(
                        f"Account '{account.account_name}' is generic or transitional "
                        "and needs documented rationale and closure logic."
                    ),
                    source=FindingSource.HEURISTIC,
                    severity_hint=FindingSeverity.MEDIUM,
                    confidence_hint=0.82,
                    evidence=[evidence_from_process(account.evidence)],
                )
            )
        return findings

    def _missing_debit_or_credit_findings(
        self,
        process: AccountingProcess,
    ) -> list[Inconsistency]:
        roles = {account.role for account in process.account_references}
        if not process.account_references:
            return []
        if AccountReferenceRole.DEBIT in roles and AccountReferenceRole.CREDIT in roles:
            return []

        evidence = process.account_references[0].evidence
        return [
            Inconsistency(
                id="heuristic-unbalanced-posting-roles",
                type=InconsistencyType.POSTING_LOGIC,
                title="Posting logic does not describe both debit and credit sides",
                description=(
                    "The structured process references account usage but does not "
                    "clearly identify both debit and credit sides of the entry."
                ),
                source=FindingSource.HEURISTIC,
                severity_hint=FindingSeverity.MEDIUM,
                confidence_hint=0.75,
                evidence=[evidence_from_process(evidence)],
            )
        ]

    def _missing_support_findings(
        self,
        process: AccountingProcess,
    ) -> list[Inconsistency]:
        combined_text = self._combined_process_text(process)
        if any(term in combined_text for term in SUPPORT_TERMS):
            return []

        return [
            Inconsistency(
                id="heuristic-missing-support",
                type=InconsistencyType.DOCUMENTARY_GAP,
                title="Supporting evidence or rationale is not documented",
                description=(
                    "The process narrative does not clearly mention supporting "
                    "documentation, evidence, invoice, memo, or accounting rationale."
                ),
                source=FindingSource.HEURISTIC,
                severity_hint=FindingSeverity.MEDIUM,
                confidence_hint=0.68,
                evidence=self._first_step_evidence(process),
            )
        ]

    def _missing_control_findings(
        self,
        process: AccountingProcess,
    ) -> list[Inconsistency]:
        if process.controls:
            return []
        combined_text = self._combined_process_text(process)
        if any(term in combined_text for term in CONTROL_TERMS):
            return []

        return [
            Inconsistency(
                id="heuristic-missing-control",
                type=InconsistencyType.CONTROL_GAP,
                title="Posting process lacks an explicit control or review step",
                description=(
                    "The structured process does not identify approval, review, "
                    "reconciliation, or another control around posting."
                ),
                source=FindingSource.HEURISTIC,
                severity_hint=FindingSeverity.MEDIUM,
                confidence_hint=0.7,
                evidence=self._first_step_evidence(process),
            )
        ]

    def _narrative_gap_findings(
        self,
        process: AccountingProcess,
    ) -> list[Inconsistency]:
        findings: list[Inconsistency] = []
        seen: set[str] = set()
        for index, gap in enumerate(process.narrative_gaps):
            if not self._is_informative_gap(gap.description):
                continue
            semantic_key = self._semantic_gap_key(gap.description)
            if semantic_key in seen:
                continue
            seen.add(semantic_key)
            finding_type = self._narrative_gap_type(gap.description)
            severity = self._narrative_gap_severity(gap.description)
            findings.append(
                Inconsistency(
                    id=f"heuristic-narrative-gap-{index}",
                    type=finding_type,
                    title=self._narrative_gap_title(gap.description, finding_type),
                    description=gap.description,
                    source=FindingSource.HEURISTIC,
                    severity_hint=severity,
                    confidence_hint=0.8 if severity != FindingSeverity.LOW else 0.76,
                    evidence=[evidence_from_process(gap.evidence)],
                )
            )
        return findings

    def _narrative_gap_type(self, description: str) -> InconsistencyType:
        normalized = self._normalize(description)
        if self._is_missing_accounting_detail(normalized):
            return InconsistencyType.DOCUMENTARY_GAP
        if any(term in normalized for term in ("reconcile", "reconciliacao", "conciliacao")):
            return InconsistencyType.RECONCILIATION_GAP
        if any(term in normalized for term in TRACEABILITY_TERMS):
            return InconsistencyType.TRACEABILITY_GAP
        if any(term in normalized for term in CONTROL_WEAKNESS_TERMS):
            return InconsistencyType.CONTROL_GAP
        if any(term in normalized for term in OPERATIONAL_INCONSISTENCY_TERMS):
            return InconsistencyType.CONTROL_GAP
        if any(term in normalized for term in THIRD_PARTY_TERMS):
            return InconsistencyType.THIRD_PARTY_DEPENDENCY
        return InconsistencyType.DOCUMENTARY_GAP

    def _narrative_gap_severity(self, description: str) -> FindingSeverity:
        normalized = self._normalize(description)
        if self._is_missing_accounting_detail(normalized):
            return FindingSeverity.LOW
        if any(term in normalized for term in TRACEABILITY_TERMS + THIRD_PARTY_TERMS):
            return FindingSeverity.MEDIUM
        if any(term in normalized for term in CONTROL_WEAKNESS_TERMS):
            return FindingSeverity.MEDIUM
        return FindingSeverity.LOW

    def _narrative_gap_title(
        self,
        description: str,
        finding_type: InconsistencyType,
    ) -> str:
        normalized = self._normalize(description)
        if self._is_missing_accounting_detail(normalized):
            return "Document does not identify accounting-entry details"
        if any(term in normalized for term in TRACEABILITY_TERMS):
            return "Narrative indicates traceability limitations"
        if any(term in normalized for term in THIRD_PARTY_TERMS):
            return "Narrative indicates third-party dependency"
        if finding_type == InconsistencyType.RECONCILIATION_GAP:
            return "Narrative indicates reconciliation gap"
        if finding_type == InconsistencyType.CONTROL_GAP:
            return "Narrative indicates control limitation"
        if finding_type == InconsistencyType.POSTING_LOGIC:
            return "Narrative indicates operational inconsistency"
        return "Narrative identifies a documentation gap"

    def _risks_from_inconsistencies(
        self,
        inconsistencies: list[Inconsistency],
    ) -> list[RiskItem]:
        risks: list[RiskItem] = []
        for inconsistency in inconsistencies:
            category = self._risk_category_for(inconsistency)
            risks.append(
                RiskItem(
                    id=f"risk-{inconsistency.id}",
                    category=category,
                    title=inconsistency.title,
                    description=self._risk_description_for(category),
                    source=inconsistency.source,
                    severity_hint=inconsistency.severity_hint,
                    confidence_hint=inconsistency.confidence_hint,
                    related_inconsistency_ids=[inconsistency.id],
                    evidence=inconsistency.evidence,
                )
            )
        return risks

    def _risk_category_for(self, inconsistency: Inconsistency) -> RiskCategory:
        normalized = self._normalize(f"{inconsistency.title} {inconsistency.description}")
        if any(term in normalized for term in TRACEABILITY_TERMS + THIRD_PARTY_TERMS):
            return RiskCategory.WEAK_CONTROL
        if any(term in normalized for term in ("reconcile", "reconciliacao", "conciliacao")):
            return RiskCategory.WEAK_CONTROL
        if inconsistency.type == InconsistencyType.ACCOUNT_USAGE:
            return RiskCategory.GENERIC_ACCOUNT_OVERUSE
        if inconsistency.type == InconsistencyType.CONTROL_GAP:
            return RiskCategory.WEAK_CONTROL
        if inconsistency.type == InconsistencyType.DOCUMENTARY_GAP:
            return RiskCategory.INSUFFICIENT_SUPPORT
        return RiskCategory.MISCLASSIFICATION

    def _risk_description_for(self, category: RiskCategory) -> str:
        descriptions = {
            RiskCategory.GENERIC_ACCOUNT_OVERUSE: (
                "Generic account usage may obscure account classification and "
                "closure responsibility."
            ),
            RiskCategory.WEAK_CONTROL: (
                "Missing review or approval increases the risk of unsupported postings."
            ),
            RiskCategory.INSUFFICIENT_SUPPORT: (
                "Missing evidence reduces traceability of the accounting entry rationale."
            ),
            RiskCategory.MISCLASSIFICATION: (
                "The entry may be classified inconsistently with the described business event."
            ),
        }
        return descriptions[category]

    def _dedupe_inconsistencies(
        self,
        inconsistencies: list[Inconsistency],
    ) -> list[Inconsistency]:
        deduped: list[Inconsistency] = []
        seen: set[str] = set()
        for inconsistency in inconsistencies:
            key = self._finding_semantic_key(inconsistency)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(inconsistency)
        return deduped

    def _dedupe_risks(self, risks: list[RiskItem]) -> list[RiskItem]:
        deduped: list[RiskItem] = []
        seen: set[tuple[str, str]] = set()
        for risk in risks:
            key = (risk.category.value, self._normalize(risk.title))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(risk)
        return deduped

    def _finding_semantic_key(self, inconsistency: Inconsistency) -> str:
        text = self._normalize(f"{inconsistency.title} {inconsistency.description}")
        if self._is_missing_accounting_detail(text):
            return "missing-accounting-entry-details"
        if any(term in text for term in TRACEABILITY_TERMS):
            return "traceability-limitation"
        if any(term in text for term in THIRD_PARTY_TERMS):
            return "third-party-dependency"
        if any(term in text for term in CONTROL_WEAKNESS_TERMS):
            return "control-weakness"
        if any(term in text for term in OPERATIONAL_INCONSISTENCY_TERMS):
            return "operational-inconsistency"
        return f"{inconsistency.type.value}:{self._compact_text_key(text)}"

    def _semantic_gap_key(self, description: str) -> str:
        normalized = self._normalize(description)
        if self._is_missing_accounting_detail(normalized):
            return "missing-accounting-entry-details"
        if any(term in normalized for term in TRACEABILITY_TERMS):
            return "traceability-limitation"
        if any(term in normalized for term in THIRD_PARTY_TERMS):
            return "third-party-dependency"
        if any(term in normalized for term in CONTROL_WEAKNESS_TERMS):
            return "control-weakness"
        if any(term in normalized for term in OPERATIONAL_INCONSISTENCY_TERMS):
            return "operational-inconsistency"
        return self._compact_text_key(normalized)

    def _is_informative_gap(self, description: str) -> bool:
        normalized = self._normalize(description).strip(" .:-")
        if normalized in {"risco", "riscos", "riscos identificados", "limitations", "limitacoes"}:
            return False
        return len(normalized.split()) >= 5

    def _is_missing_accounting_detail(self, normalized: str) -> bool:
        return (
            "not identified" in normalized
            or "were not identified" in normalized
            or "was not identified" in normalized
            or "nao foi identific" in normalized
        ) and any(
            term in normalized
            for term in (
                "account",
                "chart",
                "posting",
                "plano de contas",
                "lancamento",
            )
        )

    def _compact_text_key(self, normalized: str) -> str:
        stop_words = {
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
            "is",
            "are",
        }
        tokens = [
            token
            for token in normalized.split()
            if token and token not in stop_words
        ]
        return " ".join(tokens[:12])

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
        return " ".join(normalized.split())

    def _combined_process_text(self, process: AccountingProcess) -> str:
        return " ".join(
            [
                process.summary,
                " ".join(step.description for step in process.steps),
                " ".join(process.posting_logic),
                " ".join(control.description for control in process.controls),
            ]
        ).lower()

    def _first_step_evidence(self, process: AccountingProcess) -> list[FindingEvidence]:
        if not process.steps:
            return []
        return [evidence_from_process(process.steps[0].evidence)]

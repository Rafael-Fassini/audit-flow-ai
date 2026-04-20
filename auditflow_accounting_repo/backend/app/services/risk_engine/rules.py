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


class AccountingRiskRules:
    def evaluate(self, process: AccountingProcess) -> RiskInferenceResult:
        inconsistencies: list[Inconsistency] = []
        inconsistencies.extend(self._generic_account_findings(process))
        inconsistencies.extend(self._missing_debit_or_credit_findings(process))
        inconsistencies.extend(self._missing_support_findings(process))
        inconsistencies.extend(self._missing_control_findings(process))
        inconsistencies.extend(self._narrative_gap_findings(process))

        risks = self._risks_from_inconsistencies(inconsistencies)
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
        for index, gap in enumerate(process.narrative_gaps):
            findings.append(
                Inconsistency(
                    id=f"heuristic-narrative-gap-{index}",
                    type=InconsistencyType.DOCUMENTARY_GAP,
                    title="Narrative identifies a documentation gap",
                    description=gap.description,
                    source=FindingSource.HEURISTIC,
                    severity_hint=FindingSeverity.LOW,
                    confidence_hint=0.78,
                    evidence=[evidence_from_process(gap.evidence)],
                )
            )
        return findings

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

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AccountReferenceRole(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    UNSPECIFIED = "unspecified"


class ProcessStepType(str, Enum):
    EVENT = "event"
    APPROVAL = "approval"
    POSTING = "posting"
    REVIEW = "review"
    CONTROL = "control"
    OTHER = "other"


class EvidenceSnippet(BaseModel):
    section_index: int = Field(ge=0)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)


class AccountReference(BaseModel):
    role: AccountReferenceRole = AccountReferenceRole.UNSPECIFIED
    account_code: str | None = None
    account_name: str = Field(min_length=1)
    evidence: EvidenceSnippet

    @field_validator("account_code")
    @classmethod
    def normalize_account_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ChartOfAccountsReference(BaseModel):
    reference_text: str = Field(min_length=1)
    accounts: list[AccountReference] = Field(default_factory=list)
    evidence: EvidenceSnippet


class ControlSignal(BaseModel):
    description: str = Field(min_length=1)
    owner: str | None = None
    evidence: EvidenceSnippet


class ProcessStep(BaseModel):
    index: int = Field(ge=0)
    step_type: ProcessStepType = ProcessStepType.OTHER
    description: str = Field(min_length=1)
    actors: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    evidence: EvidenceSnippet


class NarrativeGap(BaseModel):
    description: str = Field(min_length=1)
    evidence: EvidenceSnippet


class AccountingProcess(BaseModel):
    process_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_filename: str = Field(min_length=1)
    steps: list[ProcessStep] = Field(default_factory=list)
    account_references: list[AccountReference] = Field(default_factory=list)
    chart_of_accounts_references: list[ChartOfAccountsReference] = Field(
        default_factory=list
    )
    controls: list[ControlSignal] = Field(default_factory=list)
    posting_logic: list[str] = Field(default_factory=list)
    narrative_gaps: list[NarrativeGap] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def validate_step_indexes(cls, value: list[ProcessStep]) -> list[ProcessStep]:
        expected = list(range(len(value)))
        actual = [step.index for step in value]
        if actual != expected:
            raise ValueError("Process step indexes must be sequential from zero.")
        return value

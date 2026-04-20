from app.agents.prompts.base import PromptMessage, PromptPayload, schema_instruction
from app.models.accounting_process import AccountingProcess
from app.models.report import SCOPED_ANALYSIS_QUESTION
from app.models.risk import RiskInferenceResult


def build_report_assembly_prompt(
    process: AccountingProcess,
    risk_result: RiskInferenceResult,
) -> PromptPayload:
    return PromptPayload(
        response_schema="ReportAssemblerAgentOutput",
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "You assemble short, evidence-backed structured reports from "
                    "validated process and risk-inference data. The report must answer "
                    f"only this question: {SCOPED_ANALYSIS_QUESTION} Final conclusion "
                    "must be YES, NO, or INDETERMINATE / HUMAN REVIEW REQUIRED."
                ),
            ),
            PromptMessage(
                role="user",
                content=(
                    f"{schema_instruction('ReportAssemblerAgentOutput')}\n\n"
                    f"Process:\n{process.model_dump_json()}\n\n"
                    f"Risk inference:\n{risk_result.model_dump_json()}"
                ),
            ),
        ],
    )

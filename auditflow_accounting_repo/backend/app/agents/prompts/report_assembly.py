from app.agents.prompts.base import PromptMessage, PromptPayload, schema_instruction
from app.models.accounting_process import AccountingProcess
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
                    "You assemble structured analysis reports from validated process "
                    "and risk-inference data."
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

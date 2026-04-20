from app.agents.prompts.base import PromptMessage, PromptPayload, schema_instruction
from app.models.accounting_process import AccountingProcess
from app.models.knowledge_base import RetrievalResult


def build_risk_inference_prompt(
    process: AccountingProcess,
    retrieved_context: list[RetrievalResult],
) -> PromptPayload:
    return PromptPayload(
        response_schema="RiskInferenceAgentOutput",
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "You identify accounting-entry inconsistencies, risks, and "
                    "follow-up questions using process evidence and retrieved knowledge."
                ),
            ),
            PromptMessage(
                role="user",
                content=(
                    f"{schema_instruction('RiskInferenceAgentOutput')}\n\n"
                    f"Process:\n{process.model_dump_json()}\n\n"
                    f"Retrieved context:\n{_format_context(retrieved_context)}"
                ),
            ),
        ],
    )


def _format_context(retrieved_context: list[RetrievalResult]) -> str:
    if not retrieved_context:
        return "No retrieved context was provided."
    return "\n\n".join(
        (
            f"Context {index} score={result.score:.4f} "
            f"id={result.snippet.chunk_id or result.snippet.id}:\n"
            f"{result.snippet.text}"
        )
        for index, result in enumerate(retrieved_context)
    )

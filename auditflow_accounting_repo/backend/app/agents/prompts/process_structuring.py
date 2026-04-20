from app.agents.prompts.base import PromptMessage, PromptPayload, schema_instruction
from app.models.document_section import ChunkedDocument


def build_process_structuring_prompt(document: ChunkedDocument) -> PromptPayload:
    return PromptPayload(
        response_schema="ProcessStructurerAgentOutput",
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "You structure accounting-entry process narratives into validated "
                    "process data with traceable evidence references."
                ),
            ),
            PromptMessage(
                role="user",
                content=(
                    f"{schema_instruction('ProcessStructurerAgentOutput')}\n\n"
                    f"Filename: {document.filename}\n"
                    f"Document format: {document.document_format.value}\n\n"
                    f"Chunks:\n{_format_chunks(document)}"
                ),
            ),
        ],
    )


def _format_chunks(document: ChunkedDocument) -> str:
    return "\n\n".join(
        (
            f"Chunk {chunk.index} "
            f"(section {chunk.section_index}, title={chunk.title or 'untitled'}):\n"
            f"{chunk.text}"
        )
        for chunk in document.chunks
    )

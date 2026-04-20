from app.models.document_section import DocumentFormat, ParsedDocument
from app.services.chunking.document_chunker import DocumentChunker


def test_chunker_builds_sections_from_headings() -> None:
    parsed = ParsedDocument(
        filename="walkthrough.txt",
        document_format=DocumentFormat.TXT,
        text=(
            "OVERVIEW\n\n"
            "The process starts when invoices are approved.\n\n"
            "POSTING LOGIC:\n\n"
            "The team debits expense and credits accrued liabilities."
        ),
    )

    chunked = DocumentChunker(max_chunk_chars=200).chunk(parsed)

    assert len(chunked.sections) == 2
    assert chunked.sections[0].title == "OVERVIEW"
    assert chunked.sections[1].title == "POSTING LOGIC:"
    assert len(chunked.chunks) == 2
    assert chunked.chunks[0].section_index == 0
    assert chunked.chunks[1].section_index == 1


def test_chunker_splits_long_sections_by_size() -> None:
    parsed = ParsedDocument(
        filename="policy.txt",
        document_format=DocumentFormat.TXT,
        text=(
            "POLICY\n\n"
            "First paragraph describes approval controls.\n\n"
            "Second paragraph explains account classification.\n\n"
            "Third paragraph documents posting review."
        ),
    )

    chunked = DocumentChunker(max_chunk_chars=100).chunk(parsed)

    assert len(chunked.sections) == 1
    assert len(chunked.chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunked.chunks)
    assert [chunk.index for chunk in chunked.chunks] == list(range(len(chunked.chunks)))


def test_chunker_splits_long_paragraph_without_dropping_text() -> None:
    paragraph = " ".join(["posting"] * 60)
    parsed = ParsedDocument(
        filename="long.txt",
        document_format=DocumentFormat.TXT,
        text=paragraph,
    )

    chunked = DocumentChunker(max_chunk_chars=120).chunk(parsed)

    combined = " ".join(chunk.text for chunk in chunked.chunks)
    assert len(chunked.chunks) > 1
    assert combined == paragraph

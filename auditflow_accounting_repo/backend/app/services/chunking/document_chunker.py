from app.models.document_section import (
    ChunkedDocument,
    DocumentChunk,
    DocumentSection,
    ParsedDocument,
)
from app.services.parsing.text_normalization import normalize_text


class DocumentChunker:
    def __init__(self, max_chunk_chars: int = 1200) -> None:
        if max_chunk_chars < 100:
            raise ValueError("max_chunk_chars must be at least 100.")
        self._max_chunk_chars = max_chunk_chars

    def chunk(self, document: ParsedDocument) -> ChunkedDocument:
        sections = self._build_sections(document.text)
        chunks = self._build_chunks(sections)
        return ChunkedDocument(
            filename=document.filename,
            document_format=document.document_format,
            text=document.text,
            sections=sections,
            chunks=chunks,
        )

    def _build_sections(self, text: str) -> list[DocumentSection]:
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        if not blocks:
            return []

        section_parts: list[tuple[str | None, list[str]]] = []
        current_title: str | None = None
        current_blocks: list[str] = []

        for block in blocks:
            if self._looks_like_heading(block):
                if current_blocks:
                    section_parts.append((current_title, current_blocks))
                current_title = block
                current_blocks = []
                continue
            current_blocks.append(block)

        if current_blocks:
            section_parts.append((current_title, current_blocks))

        if not section_parts:
            section_parts.append((None, blocks))

        sections: list[DocumentSection] = []
        cursor = 0
        for index, (title, body_blocks) in enumerate(section_parts):
            section_text = normalize_text("\n\n".join(body_blocks))
            start_char = text.find(section_text, cursor)
            if start_char < 0:
                start_char = cursor
            end_char = start_char + len(section_text)
            cursor = end_char
            sections.append(
                DocumentSection(
                    index=index,
                    title=title,
                    text=section_text,
                    start_char=start_char,
                    end_char=end_char,
                )
            )

        return sections

    def _build_chunks(self, sections: list[DocumentSection]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for section in sections:
            for chunk_text, start_offset in self._split_section_text(section.text):
                chunks.append(
                    DocumentChunk(
                        index=len(chunks),
                        section_index=section.index,
                        title=section.title,
                        text=chunk_text,
                        start_char=section.start_char + start_offset,
                        end_char=section.start_char + start_offset + len(chunk_text),
                    )
                )
        return chunks

    def _split_section_text(self, text: str) -> list[tuple[str, int]]:
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n")]
        chunks: list[tuple[str, int]] = []
        current = ""
        current_start = 0
        cursor = 0

        for paragraph in paragraphs:
            if not paragraph:
                cursor += 2
                continue

            paragraph_start = text.find(paragraph, cursor)
            if paragraph_start < 0:
                paragraph_start = cursor

            if len(paragraph) > self._max_chunk_chars:
                if current:
                    chunks.append((current, current_start))
                    current = ""
                chunks.extend(self._split_long_paragraph(paragraph, paragraph_start))
                cursor = paragraph_start + len(paragraph)
                continue

            candidate = paragraph if not current else current + "\n\n" + paragraph
            if current and len(candidate) > self._max_chunk_chars:
                chunks.append((current, current_start))
                current = paragraph
                current_start = paragraph_start
            else:
                if not current:
                    current_start = paragraph_start
                current = candidate

            cursor = paragraph_start + len(paragraph)

        if current:
            chunks.append((current, current_start))

        return chunks

    def _split_long_paragraph(self, paragraph: str, start: int) -> list[tuple[str, int]]:
        chunks: list[tuple[str, int]] = []
        chunk_start = 0
        while chunk_start < len(paragraph):
            chunk_end = min(chunk_start + self._max_chunk_chars, len(paragraph))
            if chunk_end < len(paragraph):
                last_space = paragraph.rfind(" ", chunk_start, chunk_end)
                if last_space > chunk_start:
                    chunk_end = last_space

            chunk = paragraph[chunk_start:chunk_end].strip()
            if chunk:
                offset = paragraph.find(chunk, chunk_start)
                chunks.append((chunk, start + offset))
            chunk_start = max(chunk_end, chunk_start + 1)
            while chunk_start < len(paragraph) and paragraph[chunk_start] == " ":
                chunk_start += 1

        return chunks

    def _looks_like_heading(self, block: str) -> bool:
        if "\n" in block or len(block) > 100:
            return False
        if block.endswith("."):
            return False
        return block.endswith(":") or block.isupper()

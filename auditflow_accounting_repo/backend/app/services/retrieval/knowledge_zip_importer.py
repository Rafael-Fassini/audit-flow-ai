import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile

from app.models.knowledge_base import (
    AuthorityLevel,
    DocumentFamily,
    DocumentScope,
    KnowledgeCategory,
    KnowledgeDocument,
    KnowledgeSnippet,
    RegimeApplicability,
)
from app.services.chunking.document_chunker import DocumentChunker
from app.services.parsing.document_parser import (
    DocumentParser,
    EmptyParsedTextError,
    UnsupportedDocumentFormatError,
)
from app.services.retrieval.knowledge_indexer import KnowledgeIndexer


SUPPORTED_KNOWLEDGE_EXTENSIONS = frozenset({".pdf", ".docx", ".txt"})


@dataclass(frozen=True)
class KnowledgeDocumentMetadata:
    document_family: DocumentFamily
    document_scope: DocumentScope
    authority_level: AuthorityLevel
    regime_applicability: RegimeApplicability
    category: KnowledgeCategory


@dataclass
class KnowledgeZipImportReport:
    source_archive: str
    supported_files: list[str] = field(default_factory=list)
    unsupported_files: list[str] = field(default_factory=list)
    duplicate_files: list[str] = field(default_factory=list)
    failed_files: dict[str, str] = field(default_factory=dict)
    indexed_chunks: int = 0


class KnowledgeZipImporter:
    def __init__(
        self,
        parser: DocumentParser,
        chunker: DocumentChunker,
        indexer: KnowledgeIndexer,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._indexer = indexer

    def import_zip(self, archive_path: Path) -> KnowledgeZipImportReport:
        report = KnowledgeZipImportReport(source_archive=archive_path.name)
        documents: list[KnowledgeDocument] = []
        seen_content_hashes: set[str] = set()

        with ZipFile(archive_path) as archive:
            for member_name in archive.namelist():
                if member_name.endswith("/"):
                    continue

                extension = Path(member_name).suffix.lower()
                if extension not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
                    report.unsupported_files.append(member_name)
                    continue

                content = archive.read(member_name)
                content_hash = self._content_hash(content)
                if content_hash in seen_content_hashes:
                    report.duplicate_files.append(member_name)
                    continue
                seen_content_hashes.add(content_hash)

                try:
                    document = self._build_knowledge_document(
                        source_archive=archive_path.name,
                        source_file=member_name,
                        content=content,
                        content_hash=content_hash,
                    )
                except (UnsupportedDocumentFormatError, EmptyParsedTextError) as exc:
                    report.failed_files[member_name] = str(exc)
                    continue

                report.supported_files.append(member_name)
                documents.append(document)

        report.indexed_chunks = self._indexer.index_documents(documents)
        return report

    def _build_knowledge_document(
        self,
        source_archive: str,
        source_file: str,
        content: bytes,
        content_hash: str,
    ) -> KnowledgeDocument:
        parsed_document = self._parser.parse(filename=source_file, content=content)
        chunked_document = self._chunker.chunk(parsed_document)
        metadata = self._classify_document(source_file)
        document_id = self._document_id(source_archive, source_file, content_hash)

        snippets = [
            self._build_snippet(
                document_id=document_id,
                source_archive=source_archive,
                source_file=source_file,
                content_hash=content_hash,
                title=Path(source_file).name,
                chunk_index=chunk.index,
                chunk_text=chunk.text,
                metadata=metadata,
            )
            for chunk in chunked_document.chunks
        ]

        return KnowledgeDocument(
            id=document_id,
            title=Path(source_file).name,
            source=f"{source_archive}:{source_file}",
            category=metadata.category,
            snippets=snippets,
        )

    def _build_snippet(
        self,
        document_id: str,
        source_archive: str,
        source_file: str,
        content_hash: str,
        title: str,
        chunk_index: int,
        chunk_text: str,
        metadata: KnowledgeDocumentMetadata,
    ) -> KnowledgeSnippet:
        chunk_hash = self._text_hash(f"{content_hash}:{chunk_index}:{chunk_text}")
        chunk_id = f"kb-{chunk_hash[:24]}"
        return KnowledgeSnippet(
            id=chunk_id,
            document_id=document_id,
            title=title,
            text=chunk_text,
            category=metadata.category,
            tags=[
                metadata.document_family.value,
                metadata.document_scope.value,
                metadata.regime_applicability.value,
            ],
            source_file=source_file,
            source_archive=source_archive,
            document_family=metadata.document_family,
            document_scope=metadata.document_scope,
            authority_level=metadata.authority_level,
            regime_applicability=metadata.regime_applicability,
            chunk_id=chunk_id,
            raw_text=chunk_text,
        )

    def _classify_document(self, source_file: str) -> KnowledgeDocumentMetadata:
        normalized = self._normalize_name(source_file)

        if "dere" in normalized or "regimes especificos" in normalized:
            return KnowledgeDocumentMetadata(
                document_family=DocumentFamily.DERE,
                document_scope=DocumentScope.REGIME_ESPECIFICO,
                authority_level=self._authority_for_dere(normalized),
                regime_applicability=self._regime_for_dere(normalized),
                category=KnowledgeCategory.POSTING_GUIDANCE,
            )

        if "lcp_214" in normalized or "lcp 214" in normalized:
            return KnowledgeDocumentMetadata(
                document_family=DocumentFamily.LC_214_2025,
                document_scope=DocumentScope.NORMA_GERAL,
                authority_level=AuthorityLevel.LEI,
                regime_applicability=RegimeApplicability.GERAL,
                category=KnowledgeCategory.ACCOUNTING_POLICY,
            )

        if "cpc_00" in normalized or "cpc 00" in normalized:
            return KnowledgeDocumentMetadata(
                document_family=DocumentFamily.NBC_TG_CPC_00_R2,
                document_scope=DocumentScope.NORMA_GERAL,
                authority_level=AuthorityLevel.LEI,
                regime_applicability=RegimeApplicability.GERAL,
                category=KnowledgeCategory.ACCOUNTING_POLICY,
            )

        if "lei_6404" in normalized or "lei 6404" in normalized or "cpc" in normalized:
            return KnowledgeDocumentMetadata(
                document_family=DocumentFamily.SOCIETARIO_GERAL,
                document_scope=DocumentScope.SOCIETARIO_GERAL,
                authority_level=AuthorityLevel.LEI,
                regime_applicability=RegimeApplicability.GERAL,
                category=KnowledgeCategory.ACCOUNTING_POLICY,
            )

        authority_level = AuthorityLevel.PDF_AUXILIAR
        if "manual" in normalized:
            authority_level = AuthorityLevel.MANUAL
        if "leiaute" in normalized:
            authority_level = AuthorityLevel.LEIAUTE

        return KnowledgeDocumentMetadata(
            document_family=DocumentFamily.OUTRO,
            document_scope=DocumentScope.NORMA_GERAL,
            authority_level=authority_level,
            regime_applicability=RegimeApplicability.GERAL,
            category=KnowledgeCategory.POSTING_GUIDANCE,
        )

    def _authority_for_dere(self, normalized_name: str) -> AuthorityLevel:
        if "regras de validacao" in normalized_name:
            return AuthorityLevel.REGRA_VALIDACAO
        if "tabelas" in normalized_name:
            return AuthorityLevel.TABELA
        if "leiaute" in normalized_name or "leiautes" in normalized_name:
            return AuthorityLevel.LEIAUTE
        if "manual" in normalized_name:
            return AuthorityLevel.MANUAL
        return AuthorityLevel.PDF_AUXILIAR

    def _regime_for_dere(self, normalized_name: str) -> RegimeApplicability:
        if "saude" in normalized_name:
            return RegimeApplicability.SAUDE
        if "prognostico" in normalized_name or "prognosticos" in normalized_name:
            return RegimeApplicability.PROGNOSTICOS
        if "financeiro" in normalized_name or "serv fin" in normalized_name:
            return RegimeApplicability.SERV_FIN
        return RegimeApplicability.GERAL

    def _document_id(
        self,
        source_archive: str,
        source_file: str,
        content_hash: str,
    ) -> str:
        value = self._text_hash(f"{source_archive}:{source_file}:{content_hash}")
        return f"doc-{value[:24]}"

    def _content_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _text_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _normalize_name(self, value: str) -> str:
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

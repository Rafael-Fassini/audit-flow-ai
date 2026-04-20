# Analysis Contracts

## Phase 0 Assessment
The current analysis API exposes two endpoints:
- `POST /analysis/reports` assembles an `AnalysisReport` from an `AccountingProcess` and `RiskInferenceResult`.
- `POST /analysis/documents/{document_id}` runs the stored-document pipeline and returns the same `AnalysisReport` response schema.

The frozen response contract is `app.models.report.AnalysisReport`. The report contains:
- `summary`
- `process`
- `findings`
- `evidence`
- `follow_up_questions`

The reusable stage contracts for a future multi-agent split are defined in `backend/app/schemas/analysis.py` with contract version `analysis.v1`.

## Current Service Flow
`DocumentAnalysisOrchestrator.analyze_document` currently executes:
1. load document metadata through `JsonDocumentRepository`
2. read the stored file bytes
3. parse with `DocumentParser`
4. chunk with `DocumentChunker`
5. structure with `AccountingProcessExtractor`
6. retrieve context with `KnowledgeRetrievalService`
7. infer risks with `HybridRiskInferenceService`
8. assemble with `AnalysisReportBuilder`
9. persist with `JsonAnalysisReportRepository`

## Reusable Services
The current parsing and retrieval components are reusable:
- `DocumentParser` extracts normalized text from PDF, DOCX, and TXT files.
- `DocumentChunker` converts parsed text into sections and chunks.
- `KnowledgeIndexer` indexes curated knowledge snippets.
- `KnowledgeRetrievalService` retrieves context for queries or structured accounting processes.
- `QdrantVectorStore` and `InMemoryVectorStore` provide vector-store boundaries.
- `DeterministicEmbeddingProvider` is suitable for deterministic local tests and MVP behavior.

## Hardcoded Config Risks
The current analysis path has several hardcoded construction choices:
- `get_document_analysis_orchestrator` directly builds Qdrant, indexing, retrieval, rules, LLM, scoring, and repositories.
- `default_knowledge_documents()` is indexed every time the orchestrator dependency is built.
- `DeterministicEmbeddingProvider` is hardwired even though OpenAI model configuration exists.
- `NoOpLLMRiskInferenceProvider` is hardwired, so `OPENAI_API_KEY` and `OPENAI_MODEL` are not used by analysis inference.
- `DocumentChunker()` uses the constructor default `max_chunk_chars=1200` instead of an explicit setting.
- `AccountingProcessExtractor` relies on module-level keyword dictionaries and heuristics.

## Target Multi-Agent Boundaries
The target contracts keep the existing orchestrated architecture and avoid autonomous runtime behavior:
- `DocumentLoadingResult`
- `DocumentParsingRequest` / `DocumentParsingResult`
- `DocumentChunkingRequest` / `DocumentChunkingResult`
- `ProcessStructuringRequest` / `ProcessStructuringResult`
- `KnowledgeRetrievalRequest` / `KnowledgeRetrievalContractResult`
- `RiskInferenceRequest` / `RiskInferenceContractResult`
- `ReportAssemblyRequest` / `ReportAssemblyResult`

Each contract carries `AnalysisContractMetadata` with `contract_version="analysis.v1"`, optional `analysis_id`, optional `document_id`, and optional `source_filename`.

## Migration Points
The typed migration inventory is `ANALYSIS_MIGRATION_POINTS` in `backend/app/schemas/analysis.py`.

Recommended migration order:
1. Move dependency construction from `app.api.analysis` into a factory module.
2. Add explicit settings for chunk size, embedding provider, LLM provider, and knowledge warm-up policy.
3. Introduce stage adapters that accept and return the typed request/result models.
4. Keep `DocumentAnalysisOrchestrator` as the runtime coordinator until stage adapters are proven by tests.
5. Replace implementation internals stage-by-stage while preserving `AnalysisReport`.

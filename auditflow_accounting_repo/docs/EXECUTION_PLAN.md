# Execution Plan

This file defines the backend + AI implementation roadmap for the AuditFlow AI MVP.

## Phase 0 — Foundation and toolchain
### Objective
Bootstrap the backend repository, runtime configuration, Docker services, and testing foundation.

### Scope
- project structure for FastAPI backend
- Dockerfile for backend
- docker-compose with backend, PostgreSQL, and Qdrant
- environment configuration
- base health endpoint
- pytest setup

### Out of scope
- upload
- document parsing
- LLM integration
- retrieval
- risk engine

### Done when
- services boot successfully with Docker Compose
- `/health` returns success
- tests run locally

### Commit checkpoints
1. `chore(repo): bootstrap backend project structure and dependencies`
2. `feat(api): add health endpoint and runtime config`
3. `test(core): add initial health tests`

## Phase 1 — Document ingestion and persistence
### Objective
Accept input documents, persist metadata, and store raw files/text references.

### Scope
- upload endpoint
- document metadata schema/model
- persistence of uploaded document metadata
- storage contract for input files

### Out of scope
- advanced parsing
- knowledge indexing
- analysis generation

### Done when
- user can upload a supported file
- metadata is stored
- endpoint returns stored document id/status

### Commit checkpoints
1. `feat(upload): add document upload endpoint`
2. `feat(storage): persist uploaded document metadata`
3. `test(upload): add integration tests for document upload`

## Phase 2 — Parsing and chunking
### Objective
Extract text from supported formats and organize it into normalized sections/chunks.

### Scope
- PDF parsing
- DOCX parsing
- TXT handling
- normalization utilities
- section/chunk models

### Out of scope
- LLM extraction
- retrieval
- inconsistency detection

### Done when
- parsed text is produced for supported input types
- sections/chunks can be persisted or passed downstream
- parser tests cover main formats

### Commit checkpoints
1. `feat(parsing): extract text from pdf docx and txt`
2. `feat(chunking): add document sectioning and chunk preparation`
3. `test(parsing): add parser and chunking tests`

## Phase 3 — Domain schemas and process structuring
### Objective
Define the accounting-entry domain schemas and build the structured process extraction stage.

### Scope
- Pydantic schemas for accounting process domain
- chart-of-accounts related schemas
- structured extraction service
- process representation persistence contract

### Out of scope
- retrieval
- final risk output
- scoring

### Done when
- a parsed document can be transformed into a structured accounting-process representation
- schema validation is enforced

### Commit checkpoints
1. `feat(schema): define accounting process and chart-of-accounts schemas`
2. `feat(extraction): implement structured accounting process extraction`
3. `test(extraction): add tests for structured extraction output`

## Phase 4 — Knowledge base ingestion and retrieval
### Objective
Create the minimal knowledge base and enable semantic retrieval.

### Scope
- knowledge base document model
- indexing pipeline for curated reference documents
- embeddings generation integration
- Qdrant collection setup
- retrieval service

### Out of scope
- final end-user report
- scoring

### Done when
- curated knowledge snippets can be indexed
- retrieval returns relevant context for a query or process structure

### Commit checkpoints
1. `feat(vector): integrate qdrant collections and client setup`
2. `feat(indexing): add knowledge base ingestion and embedding indexing`
3. `feat(retrieval): implement semantic retrieval for accounting context`
4. `test(retrieval): add retrieval integration tests`

## Phase 5 — Inconsistency and risk engine
### Objective
Build the hybrid inference layer for accounting inconsistencies and risks.

### Scope
- explicit heuristics for posting/account inconsistencies
- hybrid inference service using structured process + retrieved context + LLM
- evidence snippet mapping
- follow-up question generation

### Out of scope
- frontend visualization
- advanced explainability graphs

### Done when
- the system returns inconsistencies, risks, evidence, and follow-up questions from a structured process input

### Commit checkpoints
1. `feat(rules): add accounting inconsistency and control heuristics`
2. `feat(inference): implement hybrid inconsistency and risk inference`
3. `feat(evidence): map evidence snippets to inferred findings`
4. `test(risk-engine): add unit and integration tests for inference`

## Phase 6 — Scoring and reporting
### Objective
Score findings and generate the final structured analysis payload.

### Scope
- severity scoring
- confidence scoring
- review-required flags
- structured report schema
- final analysis assembly endpoint/service

### Out of scope
- export files
- advanced dashboards

### Done when
- the end-to-end pipeline returns a stable structured analysis payload
- the response contains summary, findings, evidence, questions, and scores

### Commit checkpoints
1. `feat(scoring): add severity and confidence scoring`
2. `feat(report): generate final structured analysis output`
3. `feat(api): expose analysis execution and result retrieval endpoints`
4. `test(pipeline): add end-to-end integration tests for analysis flow`

## Phase 7 — Hardening and documentation
### Objective
Improve reliability, observability, and developer usability.

### Scope
- structured logging
- error handling improvements
- API docs cleanup
- runbook updates
- example payloads and sample data guidance

### Out of scope
- production deployment hardening beyond MVP needs
- frontend

### Done when
- main failure cases are handled predictably
- docs are coherent
- project is runnable from clean checkout with documented steps

### Commit checkpoints
1. `feat(logging): add structured logging and request tracing`
2. `fix(errors): improve validation and service error handling`
3. `docs(runbook): finalize developer and operator documentation`

## Working protocol for the coding agent
For each phase:
1. read this file and `AGENTS.md`
2. implement only the requested phase/checkpoint
3. run relevant tests
4. summarize completed scope
5. propose the commit message listed above or a very close equivalent

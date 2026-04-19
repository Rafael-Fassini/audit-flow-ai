# AGENTS.md

## Project identity
AuditFlow AI is a backend-first AI system for **accounting entries analysis** with emphasis on the **chart of accounts**. The MVP ingests accounting process documents and produces a structured view of the process, accounting inconsistencies, risks, documentary gaps, supporting evidence, and follow-up questions.

## Product scope
The MVP analyzes documents related to the accounting entry process, such as:
- accounting memos
- walkthroughs
- accounting narratives / process descriptions
- policies and procedures
- chart of accounts documentation
- transcripts of interviews or walkthrough sessions
- optional attachments describing posting logic

The MVP must detect signals such as:
- mismatch between business event narrative and accounting entry
- potentially inappropriate account usage
- overuse of generic or transitional accounts
- incoherent classification based on the described event
- missing documentary rationale for the entry
- missing supporting evidence or control description
- fragile controls in the posting process

The MVP does **not**:
- issue final accounting opinions
- replace professional judgment
- reconcile transactional ledgers end-to-end
- implement frontend
- implement autonomous agents as the system core

## Architecture constraints
The system must follow a **modular orchestrated pipeline**, not a free-form agent.

Required high-level flow:
1. upload / ingest document
2. extract and normalize text
3. chunk and organize sections
4. structure the accounting process
5. retrieve relevant knowledge base context
6. infer inconsistencies and risks using hybrid logic
7. score severity and confidence
8. generate structured output for downstream consumers

## Mandatory stack
- Backend: FastAPI + Python 3.11+
- Schemas: Pydantic
- Database: PostgreSQL
- Vector store: Qdrant
- AI provider: OpenAI as primary option
- Testing: pytest
- Local infrastructure: Docker Compose

## Repository rules
- Do not implement frontend.
- Do not change the architecture without explicit approval.
- Do not introduce an autonomous agent framework in the MVP.
- Do not introduce heavy infra or model hosting.
- Do not expand scope beyond accounting entries + chart of accounts.
- Always work only on the phase explicitly requested from `docs/EXECUTION_PLAN.md`.

## Coding rules
- Prefer explicitness over cleverness.
- Keep modules small and cohesive.
- Use typed interfaces and validated schemas.
- Separate orchestration from business rules.
- Keep parsing, retrieval, inference, and reporting in distinct modules.
- Add docstrings only when they clarify non-obvious intent.
- Keep logging structured and minimal.

## Testing rules
Every completed phase must include relevant validation.

Expected test categories:
- unit tests for business rules, parsers, schemas, scoring, and helpers
- integration tests for API endpoints and main pipeline slices

Before concluding a phase, always run the relevant checks and report the result.

## Operational rules for the coding agent
Before coding:
1. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/EXECUTION_PLAN.md`, and `docs/COMMIT_CONVENTIONS.md`.
2. Restate the exact objective of the requested phase.
3. List the files you plan to create or modify.
4. Identify implementation risks or assumptions.

During coding:
- Touch only files needed for the current phase.
- Keep the application runnable.
- Keep tests aligned with the delivered scope.

After coding:
1. Run the relevant tests/checks.
2. Summarize what was completed.
3. List any open items explicitly.
4. Suggest the final commit message following `docs/COMMIT_CONVENTIONS.md`.

## Definition of done per phase
A phase is done only if:
- the scoped functionality is implemented
- the relevant tests pass
- code is coherent with the defined architecture
- no hidden scope expansion was introduced
- a clean commit message is proposed

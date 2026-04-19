# AuditFlow AI Backend

Backend and AI pipeline for the AuditFlow AI MVP focused on **accounting entries** and the **chart of accounts**.

## Goal
The system ingests accounting-process documents and produces a structured analysis containing:
- process summary
- process steps / flow representation
- accounting inconsistencies
- risks
- documentary gaps
- suggested follow-up questions
- evidence snippets
- severity and confidence scores

## Current MVP scope
- Backend only
- No authentication
- Single process focus: accounting entries
- Domain emphasis: chart of accounts
- Inputs: PDF, DOCX, TXT, narratives, policies, walkthroughs, transcripts
- Outputs: structured analysis payload for downstream consumers

## Core architecture
The backend follows a modular pipeline:
1. ingestion
2. parsing
3. chunking
4. process structuring
5. retrieval
6. inconsistency/risk inference
7. scoring
8. reporting

See `docs/ARCHITECTURE.md` for the full technical view.

## Tech stack
- FastAPI
- Python 3.11+
- PostgreSQL
- Qdrant
- OpenAI API (primary)
- pytest
- Docker Compose

## Local ports
- Backend API: `8000`
- PostgreSQL: `5432`
- Qdrant HTTP: `6333`
- Qdrant gRPC: `6334`

## Environment setup
Copy `.env.example` to `.env` and fill the required values.

## Run with Docker
```bash
cp .env.example .env
docker compose up --build
```

## Run backend locally
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run tests
From `backend/`:
```bash
pytest -q
```

## Documentation
- Architecture: `docs/ARCHITECTURE.md`
- Execution plan: `docs/EXECUTION_PLAN.md`
- Commit conventions: `docs/COMMIT_CONVENTIONS.md`
- Runbook: `docs/RUNBOOK.md`

## Backend structure
```text
backend/
  app/
    api/
    core/
    db/
    models/
    repositories/
    schemas/
    services/
      ingestion/
      parsing/
      chunking/
      extraction/
      retrieval/
      risk_engine/
      scoring/
      reporting/
    utils/
  tests/
    unit/
    integration/
```

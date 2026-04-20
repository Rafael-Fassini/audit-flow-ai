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
- Backend API with a lightweight React MVP frontend
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
- Backend API: `APP_PORT`, default `8000`
- PostgreSQL: `POSTGRES_PORT`, default `5432`
- Qdrant HTTP: `QDRANT_HTTP_PORT`, default `6333`
- Qdrant gRPC: `QDRANT_GRPC_PORT`, default `6334`

## Environment setup
Copy `.env.example` to `.env` and fill the required values. `.env.example` is
only a template; the application and Docker Compose should run from `.env` or
real environment variables.

The backend loads `.env` from the repository root even when commands are run
from `backend/`. A `backend/.env` file may also be used for local overrides.

Required application variables:
- `DATABASE_URL`
- `QDRANT_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `AGENT_PROVIDER`
- `AGENT_MODEL`
- `AGENT_TEMPERATURE`
- `AGENT_TIMEOUT_SECONDS`
- `AGENT_MAX_OUTPUT_TOKENS`

Required Docker Compose service variables:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

## Run with Docker
```bash
cp .env.example .env
# edit .env and set required secrets/URLs
docker compose up --build
```

## Run backend locally
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
# edit ../.env and set required secrets/URLs
uvicorn app.main:app --reload --host 0.0.0.0 --port "${APP_PORT:-8000}"
```

When running the backend directly on the host while PostgreSQL and Qdrant run
through Docker, use host-mapped URLs in `.env`, for example
`DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/auditflow`
and `QDRANT_URL=http://localhost:6333`.

## Run tests
From `backend/`:
```bash
pytest -q
```

## Run frontend locally
The React frontend is under `frontend/`. It is a single-screen MVP that uses the
real backend routes through a Vite `/api` proxy.

```bash
cd frontend
npm install
npm run dev
```

Open:
```text
http://localhost:5173
```

Keep the backend running on `http://localhost:8000`. The UI supports health
status, document upload, and analysis by `document_id`. Backend-wide document
listing and analysis-history retrieval are not exposed by the API yet, so the UI
only lists documents and reports stored in the current browser session.

## API usage
Interactive API docs are available at:
```text
http://localhost:${APP_PORT:-8000}/docs
```

Main endpoints:
- `GET /health`
- `POST /documents/`
- `POST /analysis/documents/{document_id}`
- `POST /analysis/reports`

All responses include an `X-Request-ID` header. Pass your own
`X-Request-ID` when you need to correlate a client call with backend logs.

Example requests:
- `docs/examples/document_upload.md`
- `docs/examples/analysis_report_request.json`

## Analyze an uploaded document
Upload a PDF, DOCX, or TXT file:
```bash
curl -i -X POST "http://localhost:${APP_PORT:-8000}/documents/" \
  -F "file=@/path/to/memorandum.pdf;type=application/pdf"
```

Use the returned `id` to run the end-to-end backend pipeline:
```bash
curl -i -X POST "http://localhost:${APP_PORT:-8000}/analysis/documents/<document_id>" \
  -H "X-Request-ID: memo-analysis-1"
```

The response is an `AnalysisReport` JSON payload containing the structured
process, findings, evidence, follow-up questions, severity, confidence, and
review flags. Reports are also persisted to `ANALYSIS_REPORT_PATH`.

## Documentation
- Architecture: `docs/ARCHITECTURE.md`
- Execution plan: `docs/EXECUTION_PLAN.md`
- Commit conventions: `docs/COMMIT_CONVENTIONS.md`
- Runbook: `docs/RUNBOOK.md`

## Backend structure
```text
backend/
  app/
    agents/
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

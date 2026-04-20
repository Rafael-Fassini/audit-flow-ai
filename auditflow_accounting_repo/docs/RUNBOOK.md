# Runbook

## Services
- Backend API: port 8000
- PostgreSQL: port 5432
- Qdrant: port 6333

## Start with Docker
```bash
cp .env.example .env
# edit .env and set required secrets/URLs
docker compose up --build
```

## Check health
API:
```bash
curl "http://localhost:${APP_PORT:-8000}/health"
```

Qdrant:
```bash
curl "http://localhost:${QDRANT_HTTP_PORT:-6333}/collections"
```

## API docs and request tracing
OpenAPI docs are available at:
```text
http://localhost:${APP_PORT:-8000}/docs
```

Each API response includes an `X-Request-ID` header. Clients may provide this
header, and the backend will preserve it:
```bash
curl "http://localhost:${APP_PORT:-8000}/health" \
  -H "X-Request-ID: local-health-1"
```

Backend request logs are structured JSON on stdout. The main fields are:
- `timestamp`
- `level`
- `logger`
- `message`
- `request_id`
- `method`
- `path`
- `status_code`
- `duration_ms`

Do not log request bodies, uploaded document contents, API keys, database URLs,
or client confidential data.

## Error responses
HTTP errors keep FastAPI-compatible `detail` output and add a structured
`error` object:
```json
{
  "detail": "Supported document types are PDF, DOCX, and TXT.",
  "error": {
    "code": "unsupported_media_type",
    "message": "Supported document types are PDF, DOCX, and TXT.",
    "request_id": "local-upload-1",
    "details": null
  }
}
```

Validation failures use `error.code=validation_error`, with the validation
items repeated in `error.details` for clients that need stable error metadata.

## Example payloads and sample data
Example requests live under:
```text
docs/examples/
```

Use `docs/examples/document_upload.md` for document upload commands.
Use `docs/examples/analysis_report_request.json` as the minimal structured
payload for `POST /analysis/reports`.

Sample documents should be synthetic and small. Include enough accounting
context to exercise the pipeline:
- business event narrative
- chart-of-accounts references
- posting logic
- approval or review controls
- supporting evidence or known gaps

Avoid real client files, secrets, personal data, and production ledgers in local
sample data.

## Local backend run
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
# edit ../.env and set required secrets/URLs
uvicorn app.main:app --reload --host 0.0.0.0 --port "${APP_PORT:-8000}"
```

## Test execution
```bash
cd backend
pytest -q
```

## Knowledge base zip import
Place curated knowledge-base packages under:
```bash
backend/knowledge_base/imports/
```

Import a zip into Qdrant from `backend/`:
```bash
python scripts/import_knowledge_zip.py knowledge_base/imports/recommended_kb_docs_package_atualizado.zip
```

The importer reuses the existing parsing, chunking, embedding, and indexing
pipeline. Supported files are:
- `.pdf`
- `.docx`
- `.txt`

Unsupported files are skipped and reported. Duplicate files with identical
content inside the same zip are skipped to avoid repeated chunks.

### Knowledge scope metadata
Every indexed chunk must carry these metadata fields:
- `source_file`
- `source_archive`
- `document_family`
- `document_scope`
- `authority_level`
- `regime_applicability`
- `chunk_id`
- `raw_text`

Allowed taxonomy:
- `document_family`: `dere`, `reforma_tributaria`, `societario_geral`, `outro`
- `document_scope`: `regime_especifico`, `norma_geral`, `societario_geral`
- `authority_level`: `lei`, `manual`, `leiaute`, `tabela`, `regra_validacao`, `pdf_auxiliar`
- `regime_applicability`: `geral`, `serv_fin`, `saude`, `prognosticos`

### Avoiding DeRE overreach
DeRE documents are technical-operational references for specific regimes. They
must not be treated as general rules for every accounting or tax context.

For general questions, prefer retrieval without DeRE filters; the retrieval
service penalizes `document_family=dere` and `document_scope=regime_especifico`
when the query does not mention a specific regime.

For regime-specific questions, use metadata filters or preferences such as:
```python
retrieval_service.retrieve_for_query(
    "DeRE validation rules for health plans",
    metadata_filter={"document_family": "dere"},
    preferred_document_scope="regime_especifico",
    preferred_regime_applicability="saude",
)
```

## Environment variables
Configuration is loaded only through `app.core.config.get_settings()`.
Use `.env` for local development or real environment variables in deployed
environments. `.env.example` is a template only and is not used by
`docker-compose.yml` as a runtime env file.

Required application variables:
- `DATABASE_URL`
- `QDRANT_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Required Docker Compose service variables:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

Optional variables with defaults:
- `APP_NAME`
- `APP_ENV`
- `APP_PORT`
- `UPLOAD_STORAGE_DIR`
- `DOCUMENT_METADATA_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `KNOWLEDGE_COLLECTION_NAME`
- `EMBEDDING_VECTOR_SIZE`
- `RETRIEVAL_TOP_K`
- `POSTGRES_PORT`
- `QDRANT_HTTP_PORT`
- `QDRANT_GRPC_PORT`

## Troubleshooting
### Backend cannot connect to PostgreSQL
- confirm Docker Compose is running
- confirm `DATABASE_URL` matches service name and port

### Backend cannot connect to Qdrant
- confirm Qdrant service is healthy
- confirm `QDRANT_URL` points to `http://qdrant:6333` in Docker

### OpenAI failures
- confirm API key is present
- confirm the selected model name is valid
- inspect backend logs for provider errors

### Correlating a failing request
- repeat the request with a known `X-Request-ID`
- search backend logs for the same `request_id`
- inspect `status_code`, `path`, and `duration_ms`
- use the structured `error.code` to separate validation, upload, and server errors

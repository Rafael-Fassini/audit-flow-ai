# Runbook

## Services
- Backend API: port 8000
- PostgreSQL: port 5432
- Qdrant: port 6333

## Start with Docker
```bash
cp .env.example .env
docker compose up --build
```

## Check health
API:
```bash
curl http://localhost:8000/health
```

Qdrant:
```bash
curl http://localhost:6333/collections
```

## Local backend run
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Test execution
```bash
cd backend
pytest -q
```

## Environment variables
Required:
- `APP_NAME`
- `APP_ENV`
- `APP_PORT`
- `DATABASE_URL`
- `QDRANT_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

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

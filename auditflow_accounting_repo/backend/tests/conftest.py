import os

import pytest


os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-api-key")
os.environ.setdefault("OPENAI_MODEL", "test-model")
os.environ.setdefault("AGENT_PROVIDER", "openai")
os.environ.setdefault("AGENT_MODEL", "test-agent-model")
os.environ.setdefault("AGENT_TEMPERATURE", "0.1")
os.environ.setdefault("AGENT_TIMEOUT_SECONDS", "30")
os.environ.setdefault("AGENT_MAX_OUTPUT_TOKENS", "2048")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.anyio
async def test_healthcheck_returns_ok() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_accept_environment_overrides() -> None:
    settings = Settings(
        app_name="AuditFlow Test",
        app_env="test",
        app_port=9000,
        database_url="postgresql+psycopg://user:pass@db:5432/app",
        qdrant_url="http://qdrant:6333",
        openai_api_key="secret",
        openai_model="gpt-test",
        agent_provider="openai",
        agent_model="gpt-agent-test",
        agent_temperature=0.1,
        agent_timeout_seconds=30,
        agent_max_output_tokens=2048,
    )

    assert settings.app_name == "AuditFlow Test"
    assert settings.app_env == "test"
    assert settings.app_port == 9000

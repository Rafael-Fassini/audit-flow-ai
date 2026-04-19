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
    settings = Settings(app_name="AuditFlow Test", app_env="test", app_port=9000)

    assert settings.app_name == "AuditFlow Test"
    assert settings.app_env == "test"
    assert settings.app_port == 9000

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.anyio
async def test_openapi_available() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "AuditFlow AI Backend"
    assert payload["info"]["version"] == "0.1.0"
    assert "paths" in payload
    assert "/health" in payload["paths"]
    assert "/analysis/reports" in payload["paths"]

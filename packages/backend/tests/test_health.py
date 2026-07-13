import asyncio
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient, Response

from app.core.database import MongoDatabase
from app.main import app


def request(path: str) -> Response:
    async def send_request() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(send_request())


def test_liveness() -> None:
    response = request("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_when_database_is_connected() -> None:
    with patch.object(MongoDatabase, "ping", new=AsyncMock(return_value=True)):
        response = request("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_readiness_when_database_is_unavailable() -> None:
    with patch.object(MongoDatabase, "ping", new=AsyncMock(return_value=False)):
        response = request("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}

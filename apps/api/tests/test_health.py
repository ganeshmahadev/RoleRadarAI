from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_health_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/database")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "detail": None}


async def test_cors_allows_web_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

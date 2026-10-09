from httpx import AsyncClient


async def preflight(client: AsyncClient, origin: str):
    return await client.options(
        "/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )


async def test_allowed_origin_passes_preflight(client: AsyncClient) -> None:
    response = await preflight(client, "http://localhost:3000")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_unknown_origin_is_not_allowed(client: AsyncClient) -> None:
    response = await preflight(client, "https://evil.example")

    assert "access-control-allow-origin" not in response.headers

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository

VALID = {
    "name": "Rahim Uddin",
    "phone": "+8801711000000",
    "email": "Rahim@Example.com",
    "password": "strongpass123",
}


async def register(client: AsyncClient, **overrides) -> dict:
    response = await client.post("/auth/register", json={**VALID, **overrides})
    return {"status": response.status_code, "body": response.json()}


async def test_register_creates_citizen(client: AsyncClient) -> None:
    result = await register(client)

    assert result["status"] == 201
    body = result["body"]
    assert body["role"] == "citizen"
    assert body["phone"] == VALID["phone"]
    assert body["email"] == "rahim@example.com"  # stored lowercase
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body


async def test_register_stores_only_a_hash(client: AsyncClient, db_session: AsyncSession) -> None:
    await register(client)

    user = await db_session.scalar(select(User).where(User.phone == VALID["phone"]))
    assert user is not None
    assert user.password_hash != VALID["password"]
    assert verify_password(VALID["password"], user.password_hash)


async def test_register_ignores_client_role(client: AsyncClient) -> None:
    result = await register(client, role="super_admin", is_active=False)

    assert result["status"] == 201
    assert result["body"]["role"] == "citizen"
    assert result["body"]["is_active"] is True


async def test_register_without_email(client: AsyncClient) -> None:
    result = await register(client, email=None)

    assert result["status"] == 201
    assert result["body"]["email"] is None


async def test_duplicate_phone_is_409(client: AsyncClient) -> None:
    await register(client)
    result = await register(client, email="other@example.com")

    assert result["status"] == 409
    assert result["body"]["error"]["code"] == "CONFLICT"
    assert [d["field"] for d in result["body"]["error"]["details"]] == ["phone"]


async def test_duplicate_email_ignores_case(client: AsyncClient) -> None:
    await register(client)
    result = await register(client, phone="+8801811000000", email="RAHIM@example.com")

    assert result["status"] == 409
    assert [d["field"] for d in result["body"]["error"]["details"]] == ["email"]


async def test_duplicate_phone_and_email_reports_both(client: AsyncClient) -> None:
    await register(client)
    result = await register(client)

    assert result["status"] == 409
    fields = {d["field"] for d in result["body"]["error"]["details"]}
    assert fields == {"phone", "email"}


async def test_race_past_precheck_still_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two requests can both pass the pre-check; the unique constraint must still win."""
    await register(client)

    async def not_found(self, value):
        return None

    monkeypatch.setattr(UserRepository, "get_by_phone", not_found)
    monkeypatch.setattr(UserRepository, "get_by_email", not_found)
    result = await register(client, email=None)

    assert result["status"] == 409
    assert [d["field"] for d in result["body"]["error"]["details"]] == ["phone"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("phone", "01711000000"),  # missing +880
        ("phone", "+8801211000000"),  # operator digit must be 3-9
        ("phone", "+880171100000"),  # too short
        ("password", "short"),
        ("password", "অ" * 25),  # 75 bytes > bcrypt's 72
        ("email", "not-an-email"),
        ("name", " a "),
    ],
)
async def test_invalid_input_is_422(client: AsyncClient, field: str, value: str) -> None:
    result = await register(client, **{field: value})

    assert result["status"] == 422
    error = result["body"]["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in [d["field"] for d in error["details"]]


async def test_malformed_json_is_422_on_body(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", content="{oops", headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "body"


async def test_missing_fields_are_listed(client: AsyncClient) -> None:
    response = await client.post("/auth/register", json={})

    assert response.status_code == 422
    fields = {d["field"] for d in response.json()["error"]["details"]}
    assert fields == {"name", "phone", "password"}

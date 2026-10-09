from datetime import UTC, datetime, timedelta

import jwt
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from tests.factories import PASSWORD, auth, make_user


async def login(client: AsyncClient, phone: str, password: str = PASSWORD):
    return await client.post("/auth/login", json={"phone": phone, "password": password})


# --- login -------------------------------------------------------------------------------


async def test_login_returns_token_pair(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await make_user(db_session)

    response = await login(client, user.phone)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == user.id


async def test_wrong_password_and_unknown_phone_look_the_same(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)

    wrong_password = await login(client, user.phone, "not-the-password")
    unknown_phone = await login(client, "+8801999999999")

    assert wrong_password.status_code == unknown_phone.status_code == 401
    assert wrong_password.json() == unknown_phone.json()
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_inactive_user_cannot_log_in(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await make_user(db_session, is_active=False)

    response = await login(client, user.phone)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"


# --- refresh -----------------------------------------------------------------------------


async def test_refresh_rotates_and_old_token_dies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    first = (await login(client, user.phone)).json()

    rotated = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    reused = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})

    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first["refresh_token"]
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "INVALID_TOKEN"
    # The new refresh token works.
    again = await client.post(
        "/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
    )
    assert again.status_code == 200


async def test_access_token_is_not_a_refresh_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    tokens = (await login(client, user.phone)).json()

    response = await client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})

    assert response.status_code == 401


async def test_refresh_for_disabled_user_is_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    tokens = (await login(client, user.phone)).json()
    user.is_active = False
    await db_session.flush()

    response = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 403


async def test_garbage_refresh_token_is_401(client: AsyncClient) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": "not.a.jwt"})

    assert response.status_code == 401


# --- logout ------------------------------------------------------------------------------


async def test_logout_revokes_only_that_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    phone_session = (await login(client, user.phone)).json()
    laptop_session = (await login(client, user.phone)).json()

    response = await client.post(
        "/auth/logout",
        json={"refresh_token": phone_session["refresh_token"]},
        headers=auth(user),
    )

    assert response.status_code == 204
    dead = await client.post(
        "/auth/refresh", json={"refresh_token": phone_session["refresh_token"]}
    )
    alive = await client.post(
        "/auth/refresh", json={"refresh_token": laptop_session["refresh_token"]}
    )
    assert dead.status_code == 401
    assert alive.status_code == 200


async def test_cannot_log_out_someone_elses_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    victim = await make_user(db_session)
    attacker = await make_user(db_session)
    victim_tokens = (await login(client, victim.phone)).json()

    response = await client.post(
        "/auth/logout",
        json={"refresh_token": victim_tokens["refresh_token"]},
        headers=auth(attacker),
    )

    assert response.status_code == 401
    still_valid = await client.post(
        "/auth/refresh", json={"refresh_token": victim_tokens["refresh_token"]}
    )
    assert still_valid.status_code == 200


# --- current user ------------------------------------------------------------------------


async def test_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_access_token_is_401(client: AsyncClient, db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "jti": "00000000-0000-0000-0000-000000000000",
            "iat": past - timedelta(minutes=15),
            "exp": past,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


async def test_token_signed_with_other_key_is_401(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session)
    forged = jwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "jti": "00000000-0000-0000-0000-000000000000",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "attacker-secret-attacker-secret-attacker-secret",
        algorithm="HS256",
    )

    response = await client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


async def test_disabled_user_with_valid_token_is_403(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await make_user(db_session, is_active=False)

    response = await client.get("/users/me", headers=auth(user))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DISABLED"

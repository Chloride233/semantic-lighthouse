import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import RefreshToken, User
from semantic_lighthouse.security import hash_secret, verify_password


def test_register_hashes_password(client, db_session: Session):
    response = client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )

    assert response.status_code == 201
    user = db_session.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert user.password_hash != "Passw0rd!"
    assert verify_password("Passw0rd!", user.password_hash)


def test_login_sets_short_access_token_and_http_only_refresh_cookie(client):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )

    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "Passw0rd!"})

    assert response.status_code == 200
    assert "access_token" in response.json()
    cookie_header = response.headers["set-cookie"]
    assert "semantic_lighthouse_refresh=" in cookie_header
    assert "HttpOnly" in cookie_header

    payload = jwt.decode(response.json()["access_token"], "test-secret-key-at-least-32-bytes", algorithms=["HS256"])
    assert payload["token_type"] == "access"
    assert payload["sub"]
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_wrong_password_is_rejected(client):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )

    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "wrong"})

    assert response.status_code == 401


def test_me_requires_access_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )
    login_response = client.post("/auth/login", json={"email": "owner@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_refresh_token_is_rotated_and_not_stored_plaintext(client, db_session: Session):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )
    login_response = client.post("/auth/login", json={"email": "owner@example.com", "password": "Passw0rd!"})
    old_refresh = login_response.cookies.get("semantic_lighthouse_refresh")

    token_before = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_secret(old_refresh)))
    assert token_before is not None
    assert token_before.token_hash != old_refresh

    refresh_response = client.post("/auth/refresh")

    assert refresh_response.status_code == 200
    db_session.refresh(token_before)
    assert token_before.revoked_at is not None
    assert refresh_response.cookies.get("semantic_lighthouse_refresh") != old_refresh


def test_replayed_refresh_token_revokes_family(client, db_session: Session):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )
    login_response = client.post("/auth/login", json={"email": "owner@example.com", "password": "Passw0rd!"})
    old_refresh = login_response.cookies.get("semantic_lighthouse_refresh")

    first_refresh = client.post("/auth/refresh")
    assert first_refresh.status_code == 200
    new_refresh = first_refresh.cookies.get("semantic_lighthouse_refresh")

    client.cookies.set("semantic_lighthouse_refresh", old_refresh)
    replay_response = client.post("/auth/refresh")

    assert replay_response.status_code == 401
    new_token = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_secret(new_refresh)))
    db_session.refresh(new_token)
    assert new_token.revoked_at is not None


def test_logout_revokes_refresh_token(client, db_session: Session):
    client.post(
        "/auth/register",
        json={"email": "owner@example.com", "password": "Passw0rd!", "display_name": "Owner"},
    )
    login_response = client.post("/auth/login", json={"email": "owner@example.com", "password": "Passw0rd!"})
    refresh_value = login_response.cookies.get("semantic_lighthouse_refresh")

    logout_response = client.post("/auth/logout")

    assert logout_response.status_code == 200
    token = db_session.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_secret(refresh_value)))
    assert token.revoked_at is not None

    client.cookies.set("semantic_lighthouse_refresh", refresh_value)
    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 401

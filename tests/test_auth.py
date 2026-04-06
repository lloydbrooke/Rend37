"""
Tests for authentication routes (routers/auth.py).
"""

import pytest
import auth_utils


# ── Password hashing utilities ───────────────────────────────────────


def test_hash_password_returns_hash():
    hashed = auth_utils.hash_password("mypassword")
    assert hashed != "mypassword"
    assert len(hashed) > 20


def test_verify_password_correct():
    hashed = auth_utils.hash_password("secret")
    assert auth_utils.verify_password("secret", hashed) is True


def test_verify_password_wrong():
    hashed = auth_utils.hash_password("secret")
    assert auth_utils.verify_password("wrong", hashed) is False


def test_hash_password_truncates_long_input():
    long_pw = "a" * 100
    hashed = auth_utils.hash_password(long_pw)
    # Should hash without error (truncated to 72 chars)
    assert hashed is not None


# ── JWT tokens ───────────────────────────────────────────────────────


def test_create_access_token():
    token = auth_utils.create_access_token(data={"sub": "alice"})
    assert isinstance(token, str)
    assert len(token) > 0


def test_get_current_user_from_cookie_valid(client):
    """A valid JWT cookie should return the username."""
    from unittest.mock import MagicMock

    token = auth_utils.create_access_token(data={"sub": "alice"})
    request = MagicMock()
    request.cookies = {"access_token": f"Bearer {token}"}
    assert auth_utils.get_current_user_from_cookie(request) == "alice"


def test_get_current_user_from_cookie_missing():
    from unittest.mock import MagicMock

    request = MagicMock()
    request.cookies = {}
    assert auth_utils.get_current_user_from_cookie(request) is None


def test_get_current_user_from_cookie_invalid():
    from unittest.mock import MagicMock

    request = MagicMock()
    request.cookies = {"access_token": "Bearer invalid.token.here"}
    assert auth_utils.get_current_user_from_cookie(request) is None


# ── Registration routes ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_page_renders(client):
    resp = await client.get("/auth/register")
    assert resp.status_code == 200
    assert (
        "register" in resp.text.lower()
        or "sign up" in resp.text.lower()
        or "form" in resp.text.lower()
    )


@pytest.mark.asyncio
async def test_register_user_success(client):
    resp = await client.post(
        "/auth/register",
        data={
            "username": "newuser",
            "email": "new@test.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    # Should redirect to login page
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["location"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    # Register first user
    await client.post(
        "/auth/register",
        data={"username": "taken", "email": "a@test.com", "password": "pass123"},
        follow_redirects=False,
    )
    # Try same username
    resp = await client.post(
        "/auth/register",
        data={"username": "taken", "email": "b@test.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    assert "already taken" in resp.text.lower()


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/auth/register",
        data={"username": "user1", "email": "same@test.com", "password": "pass123"},
        follow_redirects=False,
    )
    resp = await client.post(
        "/auth/register",
        data={"username": "user2", "email": "same@test.com", "password": "pass123"},
    )
    assert resp.status_code == 200
    assert "already associated" in resp.text.lower()


# ── Login routes ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_page_renders(client):
    resp = await client.get("/auth/login")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_success(client, seed_users):
    resp = await client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "access_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, seed_users):
    resp = await client.post(
        "/auth/login", data={"username": "alice", "password": "wrongpassword"}
    )
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/auth/login", data={"username": "ghost", "password": "password123"}
    )
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()


@pytest.mark.asyncio
async def test_login_redirects_to_next(client, seed_users):
    resp = await client.post(
        "/auth/login",
        data={"username": "alice", "password": "password123", "next": "/events"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/events"


# ── Logout route ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_clears_cookie(auth_client):
    resp = await auth_client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    # Cookie should be cleared (set to empty or with max-age=0)
    cookie_header = resp.headers.get("set-cookie", "")
    assert "access_token" in cookie_header

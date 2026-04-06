"""
Shared fixtures for all test modules.

Uses an in-memory SQLite database so tests never touch the real rend37.db.
Provides authenticated and unauthenticated HTTP clients via httpx.
"""

import sys
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base, get_db
from main import app
import models
import auth_utils

# ── In-memory test database ─────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    """Unauthenticated async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def seed_users(db: AsyncSession):
    """Insert test users and return them. All have password 'password123'."""
    users = [
        models.User(
            username="alice",
            email="alice@test.com",
            hashed_password=auth_utils.hash_password("password123"),
        ),
        models.User(
            username="bob",
            email="bob@test.com",
            hashed_password=auth_utils.hash_password("password123"),
        ),
    ]
    db.add_all(users)
    await db.commit()
    for u in users:
        await db.refresh(u)
    return users


@pytest.fixture
async def seed_community(db: AsyncSession, seed_users):
    """Insert a test community owned by alice."""
    community = models.Community(
        name="Test Community",
        description="A test community.",
        creator_id=seed_users[0].id,
    )
    db.add(community)
    await db.commit()
    await db.refresh(community)
    return community


@pytest.fixture
async def seed_event(db: AsyncSession, seed_users, seed_community):
    """Insert a test event organized by alice in the test community."""
    from datetime import datetime, timedelta, UTC

    event = models.Event(
        title="Test Event",
        description="A test event.",
        category="Social",
        latitude=53.4084,
        longitude=-2.9916,
        location_name="Test Location",
        date_time=datetime.now(UTC) + timedelta(days=7),
        capacity_limit=10,
        community_id=seed_community.id,
        organizer_id=seed_users[0].id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@pytest.fixture
async def auth_client(seed_users):
    """Authenticated test client (logged in as alice)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Log in via the actual login endpoint to get a real cookie
        await ac.post(
            "/auth/login",
            data={"username": "alice", "password": "password123"},
            follow_redirects=False,
        )
        # The cookie is set on the redirect response and stored in ac.cookies
        yield ac


def make_auth_cookie(username: str) -> dict:
    """Helper to create an auth cookie header dict for a given username."""
    token = auth_utils.create_access_token(data={"sub": username})
    return {"access_token": f"Bearer {token}"}

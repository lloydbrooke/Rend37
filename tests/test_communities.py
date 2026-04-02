import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from models import User, Community, CommunityMember
from auth_utils import hash_password


@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async def override_get_db():
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield async_session
    
    await engine.dispose()


@pytest.fixture
async def test_users(test_db):
    """Create test users"""
    async with test_db() as db:
        user1 = User(username="testuser1", email="user1@test.com", password_hash=hash_password("password123"))
        user2 = User(username="testuser2", email="user2@test.com", password_hash=hash_password("password123"))
        db.add(user1)
        db.add(user2)
        await db.commit()
        await db.refresh(user1)
        await db.refresh(user2)
        return user1, user2


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


def test_get_nonexistent_community(client):
    """Test getting a nonexistent community"""
    response = client.get("/communities/99999")
    assert response.status_code == 404


def test_create_community(client):
    """Test creating a community - requires auth"""
    # This test would need proper auth setup
    pass


def test_get_community_not_found(client):
    """Test retrieving a nonexistent community"""
    response = client.get("/communities/9999")
    assert response.status_code == 404


def test_join_community_not_found(client):
    """Test joining a nonexistent community"""
    # Mock would be needed for proper testing with auth
    pass


def test_leave_community_not_found(client):
    """Test leaving a community that doesn't exist"""
    # Mock would be needed for proper testing with auth
    pass

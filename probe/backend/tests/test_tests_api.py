"""
Tests for /api/tests CRUD endpoints.

Uses in-memory SQLite via FastAPI dependency override.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.storage.database import Base, get_db
from app.storage import db_models  # noqa: F401 - registers ORM models

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    """Yield a test DB session instead of the real one."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Override FastAPI's database dependency for all tests
app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_test():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/tests",
            json={"url": "https://example.com", "platform": "web"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com"
    assert data["status"] == "pending"
    assert data["platform"] == "web"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_test_invalid_url():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/tests",
            json={"url": "not-a-url", "platform": "web"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tests():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.post("/api/tests", json={"url": "https://example.com"})
        response = await client.get("/api/tests")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_test_by_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_resp = await client.post(
            "/api/tests",
            json={"url": "https://example.com"},
        )
        test_id = create_resp.json()["id"]
        response = await client.get(f"/api/tests/{test_id}")
    assert response.status_code == 200
    assert response.json()["id"] == test_id


@pytest.mark.asyncio
async def test_get_test_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/tests/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_start_non_pending_test():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_resp = await client.post("/api/tests", json={"url": "https://example.com"})
        test_id = create_resp.json()["id"]
        # Start it once — changes status to running
        await client.post(f"/api/tests/{test_id}/start")
        # Second start should fail with 409
        response = await client.post(f"/api/tests/{test_id}/start")
    assert response.status_code == 409

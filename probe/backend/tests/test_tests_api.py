"""
Tests for /api/tests CRUD endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_create_test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/tests",
            json={"url": "not-a-url", "platform": "web"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tests():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create one first
        await client.post("/api/tests", json={"url": "https://example.com"})
        response = await client.get("/api/tests")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_test_by_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/tests/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_start_non_pending_test():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/tests", json={"url": "https://example.com"})
        test_id = create_resp.json()["id"]
        # Start it once
        await client.post(f"/api/tests/{test_id}/start")
        # Try again — should conflict since it's now running
        response = await client.post(f"/api/tests/{test_id}/start")
    assert response.status_code == 409

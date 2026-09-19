"""
Tests API — CRUD + start/cancel endpoints.

POST   /api/tests          — create a test
GET    /api/tests          — list all tests
GET    /api/tests/{id}     — get test by id
POST   /api/tests/{id}/start   — start a test (runs orchestrator in background)
POST   /api/tests/{id}/cancel  — cancel a running test
GET    /api/tests/{id}/events  — SSE event stream for a test
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import PlatformType, TestConfig, TestSession
from app.core.orchestrator.orchestrator import Orchestrator
from app.drivers.web.playwright.driver import WebTestDriver
from app.storage.database import get_db
from app.storage.db_models import TestModel
from app.storage.repository import TestRepository
from app.utils.errors import ApiError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# In-memory SSE queues: test_id → list[asyncio.Queue]
_sse_queues: dict[str, list[asyncio.Queue]] = {}

# Running tasks: test_id → asyncio.Task
_running_tasks: dict[str, asyncio.Task] = {}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateTestRequest(BaseModel):
    url: str
    platform: str = "web"
    config: Optional[dict] = None


class TestResponse(BaseModel):
    id: str
    url: str
    status: str
    platform: str
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


def _to_response(t: TestModel) -> TestResponse:
    return TestResponse(
        id=t.id,
        url=t.url,
        status=t.status,
        platform=t.platform,
        created_at=t.created_at,
        updated_at=t.updated_at,
        started_at=t.started_at,
        completed_at=t.completed_at,
        error_message=t.error_message,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/tests", status_code=201)
async def create_test(
    body: CreateTestRequest,
    db: AsyncSession = Depends(get_db),
) -> TestResponse:
    """Create a new test session."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="URL is required")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    platform = body.platform or "web"
    if platform not in ("web",):
        raise HTTPException(status_code=422, detail=f"Platform '{platform}' not supported in V1")

    config_dict = body.config or {}

    test = TestModel(
        url=url,
        platform=platform,
        status="pending",
        config=config_dict,
    )

    repo = TestRepository(db)
    test = await repo.create(test)
    logger.info("test_created_api", component="api", event="create_test", test_id=test.id)
    return _to_response(test)


@router.get("/tests")
async def list_tests(
    db: AsyncSession = Depends(get_db),
) -> list[TestResponse]:
    """List all test sessions, most recent first."""
    repo = TestRepository(db)
    tests = await repo.list_all()
    return [_to_response(t) for t in tests]


@router.get("/tests/{test_id}")
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> TestResponse:
    """Get a test session by ID."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")
    return _to_response(test)


@router.post("/tests/{test_id}/start")
async def start_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start a pending test. Runs the orchestrator as a background task."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")
    if test.status not in ("pending",):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot start test in status '{test.status}'",
        )
    if test_id in _running_tasks and not _running_tasks[test_id].done():
        raise HTTPException(status_code=409, detail="Test is already running")

    session = TestSession(
        id=test.id,
        url=test.url,
        platform=PlatformType(test.platform),
        config=TestConfig(**(test.config or {})),
    )

    driver = WebTestDriver(session=session, config=session.config)

    async def _run_with_db() -> None:
        """Run orchestrator with its own DB session."""
        from app.storage.database import AsyncSessionLocal
        async with AsyncSessionLocal() as run_db:
            try:
                run_repo = TestRepository(run_db)

                async def emit(event: dict) -> None:
                    await _broadcast(test_id, event)

                orch = Orchestrator(
                    driver=driver,
                    session=session,
                    repository=run_repo,
                    event_callback=emit,
                )
                await orch.run()
                await run_db.commit()
            except Exception as exc:
                await run_db.rollback()
                logger.error(
                    "run_task_error",
                    component="api",
                    test_id=test_id,
                    error=str(exc),
                )
            finally:
                await _close_queues(test_id)

    task = asyncio.create_task(_run_with_db())
    _running_tasks[test_id] = task

    logger.info("test_started", component="api", event="start_test", test_id=test_id)
    return {"status": "started", "test_id": test_id}


@router.post("/tests/{test_id}/cancel")
async def cancel_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a running test."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

    task = _running_tasks.get(test_id)
    if task and not task.done():
        task.cancel()
        await repo.update_status(test_id, "cancelled")
        await _broadcast(test_id, {"type": "status", "status": "cancelled", "message": "Cancelled by user"})
        await _close_queues(test_id)
        logger.info("test_cancelled", component="api", event="cancel_test", test_id=test_id)
        return {"status": "cancelled", "test_id": test_id}

    return {"status": test.status, "test_id": test_id}


@router.get("/tests/{test_id}/events")
async def test_events(test_id: str, request: Request) -> StreamingResponse:
    """SSE stream for real-time test events."""
    queue: asyncio.Queue = asyncio.Queue()
    if test_id not in _sse_queues:
        _sse_queues[test_id] = []
    _sse_queues[test_id].append(queue)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    if event is None:  # sentinel — stream closed
                        break
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if test_id in _sse_queues:
                try:
                    _sse_queues[test_id].remove(queue)
                except ValueError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


async def _broadcast(test_id: str, event: dict) -> None:
    """Send an event to all SSE clients listening for this test."""
    for q in _sse_queues.get(test_id, []):
        await q.put(event)


async def _close_queues(test_id: str) -> None:
    """Send sentinel to all SSE clients so they close cleanly."""
    for q in _sse_queues.get(test_id, []):
        await q.put(None)
    _sse_queues.pop(test_id, None)

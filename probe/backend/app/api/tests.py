"""
Tests API — CRUD + start/cancel + screenshot + events endpoints.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.ai.schemas.finding_analysis import FindingAnalysisResult, TestSummaryAnalysis
from app.core.models import PlatformType, TestConfig, TestSession
from app.core.orchestrator.orchestrator import Orchestrator
from app.drivers.web.playwright.driver import WebTestDriver
from app.findings.models import Finding, FindingCategory, FindingSeverity, FindingStatus
from app.reproduction.engine import ReproductionEngine
from app.reproduction.models import ReproductionStatus
from app.storage.database import get_db
from app.storage.db_models import FindingModel, ObservationModel, ReproductionModel, TestModel
from app.storage.repository import TestRepository
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


class ActionResponse(BaseModel):
    id: str
    action_type: str
    target: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class FindingResponse(BaseModel):
    id: str
    severity: str
    category: str
    status: str = "potential"
    confidence: float = 0.8
    title: str
    description: str = ""
    evidence: list[dict[str, Any]] = []
    reproduction: Optional[dict[str, Any]] = None
    recommendation: Optional[str] = None
    ai_analysis: Optional[dict[str, Any]] = None
    fingerprint: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class ReproductionRequest(BaseModel):
    attempts: int = 1
    action_sequence: Optional[list[str]] = None


class ReproductionResponse(BaseModel):
    id: str
    test_id: str
    finding_id: str
    status: str
    attempts: int = 1
    successful_attempts: int = 0
    steps: list[str] = []
    fresh_evidence: list[dict[str, Any]] = []
    error_message: Optional[str] = None
    success: Optional[bool] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ObservationResponse(BaseModel):
    id: str
    url: str
    requested_url: str = ""
    title: str = ""
    visible_text: str = ""
    viewport: Optional[dict] = None
    page_dimensions: Optional[dict] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    element_count: int = 0
    elements_data: list = []
    console_messages: list = []
    console_errors: list = []
    js_exceptions: list = []
    failed_requests: list = []
    network_events: list = []
    fingerprint: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


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


class TestDetailResponse(TestResponse):
    current_url: Optional[str] = None
    page_title: Optional[str] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    screenshot_url: Optional[str] = None
    ai_summary: Optional[dict[str, Any]] = None
    actions: list[ActionResponse] = []
    observations: list[ObservationResponse] = []
    findings: list[FindingResponse] = []



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
    logger.info("create_test", component="api", test_id=test.id)
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
) -> TestDetailResponse:
    """Get a detailed test session by ID with latest observations, findings, and screenshot URL."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if test is None:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

    observations = await repo.get_observations(test_id)
    actions = await repo.get_actions(test_id)
    findings = await repo.get_findings(test_id)
    latest_obs = observations[-1] if observations else None
    latest_ev = await repo.get_latest_screenshot_evidence(test_id)

    has_screenshot = False
    if latest_ev and latest_ev.screenshot_path and os.path.exists(latest_ev.screenshot_path):
        has_screenshot = True
    elif latest_obs and latest_obs.screenshot_path and os.path.exists(latest_obs.screenshot_path):
        has_screenshot = True

    screenshot_url = f"/api/tests/{test_id}/screenshot" if has_screenshot else None

    # Calculate overall duration
    duration_ms: Optional[float] = None
    if latest_obs and latest_obs.duration_ms is not None:
        duration_ms = latest_obs.duration_ms
    elif test.completed_at and test.started_at:
        duration_ms = round((test.completed_at - test.started_at).total_seconds() * 1000, 2)

    return TestDetailResponse(
        id=test.id,
        url=test.url,
        status=test.status,
        platform=test.platform,
        created_at=test.created_at,
        updated_at=test.updated_at,
        started_at=test.started_at,
        completed_at=test.completed_at,
        error_message=test.error_message,
        current_url=latest_obs.url if latest_obs and latest_obs.url else test.url,
        page_title=latest_obs.title if latest_obs else "",
        duration_ms=duration_ms,
        status_code=latest_obs.status_code if latest_obs else None,
        screenshot_url=screenshot_url,
        ai_summary=test.ai_summary,
        actions=[ActionResponse.model_validate(a) for a in actions],
        observations=[ObservationResponse.model_validate(o) for o in observations],
        findings=[FindingResponse.model_validate(f) for f in findings],
    )


@router.get("/tests/{test_id}/screenshot")
async def get_test_screenshot(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Retrieve the captured screenshot for a test session."""
    from app.storage.artifacts import default_artifact_storage

    repo = TestRepository(db)
    ev = await repo.get_latest_screenshot_evidence(test_id)
    if ev and ev.screenshot_path:
        path = ev.screenshot_path
        if not os.path.isabs(path):
            path = os.path.join(default_artifact_storage.base_dir, path)
        if os.path.exists(path):
            return FileResponse(path, media_type="image/png")

    obs = await repo.get_latest_observation(test_id)
    if obs and obs.screenshot_path:
        path = obs.screenshot_path
        if not os.path.isabs(path):
            path = os.path.join(default_artifact_storage.base_dir, path)
        if os.path.exists(path):
            return FileResponse(path, media_type="image/png")

    raise HTTPException(status_code=404, detail="Screenshot not available for this test")


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

    # Mark as running in repository immediately
    await repo.update_status(test_id, "running")

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
                logger.error("run_task_error", component="api", test_id=test_id, error=str(exc))
            finally:
                await _close_queues(test_id)

    task = asyncio.create_task(_run_with_db())
    _running_tasks[test_id] = task

    logger.info("start_test", component="api", test_id=test_id)
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
        logger.info("cancel_test", component="api", test_id=test_id)
        return {"status": "cancelled", "test_id": test_id}

    return {"status": test.status, "test_id": test_id}


@router.post("/tests/{test_id}/findings/{finding_id}/reproduce", response_model=ReproductionResponse)
async def reproduce_finding(
    test_id: str,
    finding_id: str,
    body: Optional[ReproductionRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> ReproductionResponse:
    """Attempt deterministic reproduction of a finding."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

    findings = await repo.get_findings(test_id)
    finding_model = next((f for f in findings if f.id == finding_id), None)
    if not finding_model:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")

    finding = Finding(
        id=finding_model.id,
        test_id=test_id,
        title=finding_model.title,
        category=FindingCategory(finding_model.category) if finding_model.category in [c.value for c in FindingCategory] else FindingCategory.OTHER,
        severity=FindingSeverity(finding_model.severity) if finding_model.severity in [s.value for s in FindingSeverity] else FindingSeverity.MEDIUM,
        status=FindingStatus(finding_model.status) if finding_model.status in [st.value for st in FindingStatus] else FindingStatus.POTENTIAL,
        confidence=finding_model.confidence,
        description=finding_model.description,
        evidence=finding_model.evidence or [],
        reproduction=finding_model.reproduction,
        recommendation=finding_model.recommendation,
        fingerprint=finding_model.fingerprint,
        timestamp=finding_model.timestamp,
    )

    req = body or ReproductionRequest()
    session = TestSession(
        id=test.id,
        url=test.url,
        platform=PlatformType(test.platform),
        config=TestConfig(**(test.config or {})),
    )

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        engine = ReproductionEngine(driver=driver, session=session, repository=repo)
        result = await engine.reproduce(
            finding=finding,
            attempts=req.attempts,
            action_sequence=req.action_sequence,
        )
        await db.commit()

        # Broadcast finding update and reproduction result
        await _broadcast(test_id, {
            "type": "finding_reproduced",
            "finding_id": finding.id,
            "status": finding.status.value,
            "reproduction_status": result.status.value,
            "successful_attempts": result.successful_attempts,
            "attempts": result.attempts,
        })

        return ReproductionResponse(
            id=result.id,
            test_id=result.test_id,
            finding_id=result.finding_id,
            status=result.status.value,
            attempts=result.attempts,
            successful_attempts=result.successful_attempts,
            steps=result.action_sequence,
            fresh_evidence=result.fresh_evidence,
            error_message=result.error_message,
            success=(result.status == ReproductionStatus.REPRODUCED),
            created_at=result.started_at,
            completed_at=result.completed_at,
        )
    finally:
        await driver.close()


@router.get("/tests/{test_id}/findings/{finding_id}/reproductions", response_model=list[ReproductionResponse])
async def list_reproductions(
    test_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ReproductionResponse]:
    """List reproduction attempts for a finding."""
    repo = TestRepository(db)
    reps = await repo.get_reproductions_for_finding(finding_id)
    return [
        ReproductionResponse(
            id=r.id,
            test_id=r.test_id,
            finding_id=r.finding_id,
            status=r.status,
            attempts=r.attempts,
            successful_attempts=r.successful_attempts,
            steps=r.steps or [],
            fresh_evidence=r.fresh_evidence or [],
            error_message=r.error_message,
            success=r.success,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in reps
    ]


@router.get("/tests/{test_id}/findings/{finding_id}", response_model=FindingResponse)
async def get_finding(
    test_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    """Get detailed finding by ID."""
    repo = TestRepository(db)
    findings = await repo.get_findings(test_id)
    f = next((item for item in findings if item.id == finding_id), None)
    if not f:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    return FindingResponse.model_validate(f)


@router.post("/tests/{test_id}/findings/{finding_id}/analyze", response_model=FindingAnalysisResult)
async def analyze_finding_endpoint(
    test_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> FindingAnalysisResult:
    """Analyze a single finding using the configured AI provider."""
    repo = TestRepository(db)
    f_model = await repo.get_finding(finding_id)
    if not f_model or f_model.test_id != test_id:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found for test {test_id}")

    finding = Finding(
        id=f_model.id,
        test_id=f_model.test_id,
        title=f_model.title,
        category=FindingCategory(f_model.category) if f_model.category in [e.value for e in FindingCategory] else FindingCategory.OTHER,
        severity=FindingSeverity(f_model.severity) if f_model.severity in [e.value for e in FindingSeverity] else FindingSeverity.MEDIUM,
        status=FindingStatus(f_model.status) if f_model.status in [e.value for e in FindingStatus] else FindingStatus.POTENTIAL,
        confidence=f_model.confidence,
        description=f_model.description,
        evidence=f_model.evidence or [],
        reproduction=f_model.reproduction,
        recommendation=f_model.recommendation,
        fingerprint=f_model.fingerprint,
    )

    provider = get_ai_provider()
    analysis = await provider.analyze_finding(finding)

    # Persist analysis to finding
    f_model.ai_analysis = analysis.model_dump(mode="json")
    if analysis.recommendation and not f_model.recommendation:
        f_model.recommendation = analysis.recommendation
    await repo.update_finding(f_model)

    await _broadcast(test_id, {
        "type": "finding_analyzed",
        "finding_id": finding_id,
        "ai_analysis": f_model.ai_analysis,
    })

    return analysis


@router.post("/tests/{test_id}/analyze", response_model=TestSummaryAnalysis)
async def analyze_test_endpoint(
    test_id: str,
    db: AsyncSession = Depends(get_db),
) -> TestSummaryAnalysis:
    """Analyze overall test quality and generate executive AI summary."""
    repo = TestRepository(db)
    test = await repo.get(test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")

    finding_models = await repo.get_findings(test_id)
    findings = [
        Finding(
            id=fm.id,
            test_id=fm.test_id,
            title=fm.title,
            category=FindingCategory(fm.category) if fm.category in [e.value for e in FindingCategory] else FindingCategory.OTHER,
            severity=FindingSeverity(fm.severity) if fm.severity in [e.value for e in FindingSeverity] else FindingSeverity.MEDIUM,
            status=FindingStatus(fm.status) if fm.status in [e.value for e in FindingStatus] else FindingStatus.POTENTIAL,
            confidence=fm.confidence,
            description=fm.description,
            evidence=fm.evidence or [],
            reproduction=fm.reproduction,
            recommendation=fm.recommendation,
            fingerprint=fm.fingerprint,
        )
        for fm in finding_models
    ]

    test_dict = {
        "id": test.id,
        "url": test.url,
        "status": test.status,
        "started_at": str(test.started_at) if test.started_at else None,
        "completed_at": str(test.completed_at) if test.completed_at else None,
    }

    provider = get_ai_provider()
    summary = await provider.generate_test_summary(findings, test_dict)

    test.ai_summary = summary.model_dump(mode="json")
    await repo.update(test)

    await _broadcast(test_id, {
        "type": "test_analyzed",
        "test_id": test_id,
        "ai_summary": test.ai_summary,
    })

    return summary


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
    for q in _sse_queues.get(test_id, []):
        await q.put(event)


async def _close_queues(test_id: str) -> None:
    for q in _sse_queues.get(test_id, []):
        await q.put(None)
    _sse_queues.pop(test_id, None)

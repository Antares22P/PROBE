"""
Automated tests for PROBE real browser test execution using Playwright.

Covers:
- Browser initialization & isolated context
- Deterministic navigation & telemetry (requested URL, final URL, title, duration)
- Invalid URL & DNS failure handling
- Timeout handling
- Screenshot capture & file verification
- Full Orchestrator session lifecycle
"""
import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.models import (
    Action,
    ActionType,
    EvidenceType,
    PlatformType,
    TestConfig,
    TestSession,
)
from app.drivers.web.playwright.driver import WebTestDriver
from app.core.orchestrator.orchestrator import Orchestrator
from app.storage.database import Base
from app.storage.db_models import TestModel
from app.storage.repository import TestRepository

# Deterministic HTML test page with title, headings, and interactive elements
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <title>PROBE Real Browser Test Page</title>
</head>
<body style="background:#0f172a; color:#f8fafc; font-family:sans-serif; padding:20px;">
    <h1>PROBE Web Autonomous Tester</h1>
    <p id="desc">Deterministic local test target for Playwright.</p>
    <button id="btn-action" onclick="document.getElementById('desc').innerText='Action Clicked'">Run Action</button>
    <a id="link-target" href="#target">Learn More</a>
</body>
</html>"""

DATA_URL = f"data:text/html,{HTML_CONTENT.replace(' ', '%20').replace('#', '%23').replace('<', '%3C').replace('>', '%3E').replace('\"', '%22')}"


@pytest.fixture
def test_session():
    return TestSession(
        url=DATA_URL,
        platform=PlatformType.WEB,
        config=TestConfig(headless=True, viewport_width=1280, viewport_height=720),
    )


# ---------------------------------------------------------------------------
# 1. Browser Initialization & Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_initialization(test_session):
    driver = WebTestDriver(test_session, test_session.config)
    assert not driver.is_initialized

    await driver.initialize()
    assert driver.is_initialized
    assert driver._page is not None
    assert driver._context is not None
    assert driver._browser is not None

    await driver.close()
    assert not driver.is_initialized
    assert driver._page is None
    assert driver._context is None


# ---------------------------------------------------------------------------
# 2. Navigation & Telemetry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_navigation(test_session):
    driver = WebTestDriver(test_session, test_session.config)
    await driver.initialize()

    try:
        state = await driver.navigate(DATA_URL)
        assert state.requested_url == DATA_URL
        assert state.title == "PROBE Real Browser Test Page"
        assert state.duration_ms is not None
        assert state.duration_ms >= 0
        assert state.error is None

        # Verify interactive elements detected
        assert len(state.elements) >= 2
        tags = [el.tag for el in state.elements]
        assert "button" in tags
        assert "a" in tags
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# 3. Invalid URL & Error Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_url_protocol(test_session):
    driver = WebTestDriver(test_session, test_session.config)
    await driver.initialize()

    try:
        state = await driver.navigate("ftp://invalid-protocol.local")
        assert state.error is not None
        assert "Invalid URL" in state.error or "protocol" in state.error
        assert state.duration_ms is not None
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_dns_failure_handling(test_session):
    driver = WebTestDriver(test_session, test_session.config)
    await driver.initialize()

    try:
        # Non-existent domain should be caught cleanly
        state = await driver.navigate("https://probe-nonexistent-domain-testing-xyz999.invalid")
        assert state.error is not None
        assert any(term in state.error for term in ("DNS", "Navigation failed", "ERR_NAME_NOT_RESOLVED"))
        assert state.duration_ms is not None
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# 4. Timeout Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_navigation_timeout_handling():
    # Configure tiny timeout
    session = TestSession(
        url="https://10.255.255.1",  # Non-routable blackhole IP
        config=TestConfig(headless=True, timeout_seconds=1),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state = await driver.navigate("https://10.255.255.1")
        assert state.error is not None
        assert any(term in state.error for term in ("timed out", "timeout", "Navigation"))
        assert state.duration_ms is not None
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# 5. Screenshot Capture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_screenshot_capture(test_session):
    driver = WebTestDriver(test_session, test_session.config)
    await driver.initialize()

    try:
        await driver.navigate(DATA_URL)
        evidence = await driver.capture_screenshot()

        assert evidence.type == EvidenceType.SCREENSHOT
        assert evidence.screenshot_path is not None
        assert os.path.exists(evidence.screenshot_path)
        # Check that screenshot is a valid non-empty PNG
        file_size = os.path.getsize(evidence.screenshot_path)
        assert file_size > 500  # Non-empty image
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# 6. Full Session Lifecycle (Orchestrator End-to-End)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_session_lifecycle_end_to_end(test_session):
    # Setup test DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as db:
        repo = TestRepository(db)
        test_model = TestModel(
            id=test_session.id,
            url=test_session.url,
            platform="web",
            status="pending",
        )
        await repo.create(test_model)

        emitted_events = []

        async def capture_event(event: dict) -> None:
            emitted_events.append(event)

        driver = WebTestDriver(test_session, test_session.config)
        orch = Orchestrator(
            driver=driver,
            session=test_session,
            repository=repo,
            event_callback=capture_event,
        )

        await orch.run()

        # Check DB state
        saved_test = await repo.get(test_session.id)
        assert saved_test is not None
        assert saved_test.status == "completed"

        # Check saved observations
        obs_list = await repo.get_observations(test_session.id)
        assert len(obs_list) >= 1
        latest_obs = obs_list[-1]
        assert latest_obs.title == "PROBE Real Browser Test Page"
        assert latest_obs.screenshot_path is not None
        assert os.path.exists(latest_obs.screenshot_path)

        # Check saved evidence
        latest_ev = await repo.get_latest_screenshot_evidence(test_session.id)
        assert latest_ev is not None
        assert latest_ev.screenshot_path == latest_obs.screenshot_path

        # Check emitted SSE events
        event_types = [e["type"] for e in emitted_events]
        assert "status" in event_types
        assert "observation" in event_types
        assert "screenshot" in event_types

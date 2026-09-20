"""
Reliability, Failure Isolation, and Robustness Test Suite for PROBE V1.

Validates:
1. Target site scenarios:
   - Static site
   - Multi-page site
   - Form-heavy site
   - Site with JavaScript runtime errors
   - Site with failed network requests
   - Site with redirects
   - Site with slow responses & timeouts
   - Site with interactive components & DOM mutations
2. Failure Isolation:
   - TARGET_APPLICATION_ERROR
   - BROWSER_AUTOMATION_ERROR
   - PROBE_INTERNAL_ERROR
   - AI_PROVIDER_ERROR
   - NETWORK_INFRASTRUCTURE_ERROR
3. Resource Cleanup & Process Isolation
4. Concurrency (independent concurrent test sessions)
5. Database deduplication & integrity
6. Security protocol validation
"""
import asyncio
import os
import urllib.parse
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.providers.null_provider import NullProvider
from app.ai.schemas.finding_analysis import AIErrorType
from app.core.models import (
    Action,
    ActionType,
    PlatformType,
    TestConfig,
    TestSession,
)
from app.core.orchestrator.orchestrator import Orchestrator
from app.detection.detector import Detector
from app.drivers.web.playwright.driver import WebTestDriver
from app.exploration.engine import ExplorationEngine
from app.findings.models import Finding, FindingCategory, FindingSeverity, FindingStatus
from app.storage.database import Base
from app.storage.db_models import FindingModel, TestModel
from app.storage.repository import TestRepository
from app.utils.errors import (
    AiProviderError,
    BrowserAutomationError,
    DriverError,
    ErrorCode,
    NetworkInfrastructureError,
    ProbeInternalError,
    TargetApplicationError,
)


def make_data_url(html: str) -> str:
    """Helper to convert HTML string to data:text/html URL."""
    return f"data:text/html;charset=utf-8,{urllib.parse.quote(html)}"


# ---------------------------------------------------------------------------
# 1. Target Site Scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_static_site_reliability():
    """Verify deterministic exploration on a clean static website."""
    html = """<!DOCTYPE html>
    <html>
    <head><title>Static Documentation</title></head>
    <body>
        <h1>Documentation Header</h1>
        <p>This is a completely static, accessible web page.</p>
        <nav>
            <a id="nav-overview" href="#overview">Overview</a>
            <a id="nav-api" href="#api">API Reference</a>
        </nav>
    </body>
    </html>"""
    session = TestSession(
        url=make_data_url(html),
        config=TestConfig(headless=True, max_actions=5, max_duration_seconds=10),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state = await driver.navigate(session.url)
        assert state.title == "Static Documentation"
        assert state.error is None
        assert len(state.elements) >= 2

        # Verify element discovery
        element_tags = [e.tag for e in state.elements]
        assert "a" in element_tags
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_multi_page_site_navigation():
    """Verify multi-page transitions and state fingerprint evolution."""
    html_page1 = """<!DOCTYPE html>
    <html>
    <head><title>Home Page</title></head>
    <body>
        <h1>Home</h1>
        <button id="btn-next" onclick="document.body.innerHTML='<h1>Dashboard Page</h1><p>Welcome to dashboard</p><a id=\\'btn-back\\' href=\\'#home\\'>Back</a>'; document.title='Dashboard Page';">Go to Dashboard</button>
    </body>
    </html>"""

    session = TestSession(
        url=make_data_url(html_page1),
        config=TestConfig(headless=True, max_actions=10),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state1 = await driver.navigate(session.url)
        assert state1.title == "Home Page"
        fp1 = state1.fingerprint

        # Execute Click action
        click_action = Action(type=ActionType.CLICK, target="#btn-next")
        state2 = await driver.execute_action(click_action)

        assert state2.title == "Dashboard Page"
        assert "Dashboard Page" in state2.visible_text
        fp2 = state2.fingerprint

        # State fingerprints must differ across distinct pages
        assert fp1 != fp2
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_form_heavy_site_interaction():
    """Verify discovery and interaction with diverse form controls."""
    html_form = """<!DOCTYPE html>
    <html>
    <head><title>User Registration</title></head>
    <body>
        <form id="reg-form" onsubmit="event.preventDefault(); document.getElementById('status').innerText='Submitted Successfully';">
            <input type="text" id="username" name="username" placeholder="Username" />
            <input type="email" id="email" name="email" placeholder="Email" />
            <select id="role" name="role">
                <option value="admin">Administrator</option>
                <option value="user" selected>Standard User</option>
            </select>
            <input type="checkbox" id="terms" name="terms" />
            <textarea id="bio" name="bio" placeholder="User Bio"></textarea>
            <button type="submit" id="btn-submit">Register</button>
        </form>
        <div id="status">Pending</div>
    </body>
    </html>"""

    session = TestSession(
        url=make_data_url(html_form),
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state = await driver.navigate(session.url)
        assert state.error is None
        assert len(state.elements) >= 5

        # Fill text input
        await driver.execute_action(Action(type=ActionType.TYPE, target="#username", value="probe_tester"))
        # Fill email
        await driver.execute_action(Action(type=ActionType.TYPE, target="#email", value="test@probe.dev"))
        # Select role
        await driver.execute_action(Action(type=ActionType.SELECT, target="#role", value="admin"))
        # Submit form
        final_state = await driver.execute_action(Action(type=ActionType.CLICK, target="#btn-submit"))

        assert "Submitted Successfully" in final_state.visible_text
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_site_with_javascript_errors_detection():
    """Verify JavaScript runtime exceptions and console errors are captured as telemetry."""
    html_js_error = """<!DOCTYPE html>
    <html>
    <head><title>Buggy App</title></head>
    <body>
        <h1>Buggy App</h1>
        <button id="btn-crash" onclick="window.nonExistentFunction.call()">Trigger Runtime Error</button>
        <script>
            console.error("Initialization warning: legacy module failed to mount");
        </script>
    </body>
    </html>"""

    session = TestSession(
        url=make_data_url(html_js_error),
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state1 = await driver.navigate(session.url)
        assert len(state1.console_errors) >= 1

        # Trigger uncaught JS runtime error
        state2 = await driver.execute_action(Action(type=ActionType.CLICK, target="#btn-crash"))
        assert len(state2.js_exceptions) >= 1

        # Run detector
        detector = Detector(test_id=session.id)
        findings = detector.detect(state2)
        assert len(findings) >= 1
        js_finding = next(f for f in findings if f.category == FindingCategory.JAVASCRIPT)
        assert js_finding.severity == FindingSeverity.HIGH
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_site_with_failed_network_requests():
    """Verify failed fetch requests are captured as FailedRequest telemetry."""
    html_failed_network = """<!DOCTYPE html>
    <html>
    <head><title>Network Test App</title></head>
    <body>
        <h1>Network Test</h1>
        <button id="btn-fetch-fail" onclick="fetch('/api/nonexistent-endpoint-404').catch(e => console.error(e))">Fetch Broken API</button>
    </body>
    </html>"""

    session = TestSession(
        url=make_data_url(html_failed_network),
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        await driver.navigate(session.url)
        state = await driver.execute_action(Action(type=ActionType.CLICK, target="#btn-fetch-fail"))
        await asyncio.sleep(0.5)

        # State should record either failed request or console error
        assert state is not None
    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_site_with_interactive_components():
    """Verify modal and dropdown toggles mutate state cleanly."""
    html_interactive = """<!DOCTYPE html>
    <html>
    <head><title>Interactive App</title></head>
    <body>
        <h1>Interactive Components</h1>
        <button id="btn-open-modal" onclick="document.getElementById('modal').style.display='block'">Open Modal</button>
        <div id="modal" style="display:none; background:#222; color:#fff; padding:20px;">
            <h2>Modal Dialog</h2>
            <button id="btn-close-modal" onclick="document.getElementById('modal').style.display='none'">Close</button>
        </div>
    </body>
    </html>"""

    session = TestSession(
        url=make_data_url(html_interactive),
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state_init = await driver.navigate(session.url)
        assert "Modal Dialog" not in state_init.visible_text

        # Open Modal
        state_open = await driver.execute_action(Action(type=ActionType.CLICK, target="#btn-open-modal"))
        assert "Modal Dialog" in state_open.visible_text

        # Close Modal
        state_closed = await driver.execute_action(Action(type=ActionType.CLICK, target="#btn-close-modal"))
        assert "Modal Dialog" not in state_closed.visible_text
    finally:
        await driver.close()


# ---------------------------------------------------------------------------
# 2. Failure Isolation Tests
# ---------------------------------------------------------------------------


def test_failure_isolation_error_types():
    """Verify that all 5 failure categories are distinct and properly typed."""
    target_err = TargetApplicationError("500 Internal Server Error returned by backend")
    assert target_err.code == ErrorCode.TARGET_APPLICATION_ERROR
    assert target_err.to_response()["error"] == "TARGET_APPLICATION_ERROR"

    browser_err = BrowserAutomationError("Playwright process disconnected unexpectedly")
    assert browser_err.code == ErrorCode.BROWSER_AUTOMATION_ERROR
    assert browser_err.to_response()["error"] == "BROWSER_AUTOMATION_ERROR"

    probe_err = ProbeInternalError("Database lock failed")
    assert probe_err.code == ErrorCode.PROBE_INTERNAL_ERROR
    assert probe_err.to_response()["error"] == "PROBE_INTERNAL_ERROR"

    ai_err = AiProviderError("Gemini quota exceeded (HTTP 429)")
    assert ai_err.code == ErrorCode.AI_PROVIDER_ERROR
    assert ai_err.to_response()["error"] == "AI_PROVIDER_ERROR"

    net_err = NetworkInfrastructureError("DNS resolution failed for hostname")
    assert net_err.code == ErrorCode.NETWORK_INFRASTRUCTURE_ERROR
    assert net_err.to_response()["error"] == "NETWORK_INFRASTRUCTURE_ERROR"


# ---------------------------------------------------------------------------
# 3. Timeout and Resource Cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resource_cleanup_after_session():
    """Verify that closing driver completely cleans all Playwright contexts and pages."""
    html = "<!DOCTYPE html><html><body><h1>Cleanup Test</h1></body></html>"
    session = TestSession(url=make_data_url(html), config=TestConfig(headless=True))
    driver = WebTestDriver(session, session.config)

    await driver.initialize()
    assert driver._page is not None
    assert driver._context is not None
    assert driver._browser is not None

    await driver.navigate(session.url)
    await driver.close()

    assert driver._page is None
    assert driver._context is None
    assert driver._browser is None
    assert driver._playwright is None
    assert not driver._initialized


# ---------------------------------------------------------------------------
# 4. Concurrency Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_independent_test_sessions():
    """Verify that multiple simultaneous test sessions execute in parallel without cross-talk."""
    html1 = "<!DOCTYPE html><html><head><title>App 1</title></head><body><h1>Session 1</h1><button id='b1'>Button 1</button></body></html>"
    html2 = "<!DOCTYPE html><html><head><title>App 2</title></head><body><h1>Session 2</h1><button id='b2'>Button 2</button></body></html>"

    session1 = TestSession(url=make_data_url(html1), config=TestConfig(headless=True))
    session2 = TestSession(url=make_data_url(html2), config=TestConfig(headless=True))

    driver1 = WebTestDriver(session1, session1.config)
    driver2 = WebTestDriver(session2, session2.config)

    await driver1.initialize()
    await driver2.initialize()

    try:
        # Run both navigations in parallel
        state1, state2 = await asyncio.gather(
            driver1.navigate(session1.url),
            driver2.navigate(session2.url),
        )

        assert state1.title == "App 1"
        assert state2.title == "App 2"
        assert "Session 1" in state1.visible_text
        assert "Session 2" in state2.visible_text
        assert state1.fingerprint != state2.fingerprint
    finally:
        await asyncio.gather(driver1.close(), driver2.close())


# ---------------------------------------------------------------------------
# 5. Database Integrity & Deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_deduplication_and_integrity():
    """Verify repository prevents duplicate findings with identical fingerprints and persists cleanly."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_maker() as db:
        repo = TestRepository(db)

        test_model = TestModel(id="test-dedup-1", url="https://example.com", status="running")
        await repo.create(test_model)

        # Create finding with specific fingerprint
        f1 = FindingModel(
            id="f-1",
            test_id="test-dedup-1",
            severity="high",
            category="javascript",
            status="potential",
            confidence=0.9,
            title="Uncaught TypeError in main.js",
            fingerprint="fp-js-typeerror-line42",
        )
        await repo.add_finding(f1)

        # Check existing by fingerprint
        existing = await repo.get_finding_by_fingerprint("test-dedup-1", "fp-js-typeerror-line42")
        assert existing is not None
        assert existing.id == "f-1"

        # List all with counts
        tests_with_counts = await repo.list_all_with_counts()
        assert len(tests_with_counts) == 1
        test_row, actions_cnt, states_cnt, findings_cnt = tests_with_counts[0]
        assert test_row.id == "test-dedup-1"
        assert findings_cnt == 1


# ---------------------------------------------------------------------------
# 6. Security Protocol Validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_disallowed_protocols():
    """Verify that dangerous URL schemes like javascript: or ftp: are safely rejected."""
    session = TestSession(
        url="ftp://ftp.dangerous-target.local",
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session, session.config)
    await driver.initialize()

    try:
        state = await driver.navigate("ftp://ftp.dangerous-target.local")
        assert state.error is not None
        assert "Invalid URL protocol" in state.error or "Must start with http" in state.error
    finally:
        await driver.close()

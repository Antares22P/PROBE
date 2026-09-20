"""
Automated tests for PROBE Deterministic Issue Detection Engine (Step 05).

Tests:
1. Network Detections: HTTP 4xx, HTTP 5xx, failed network requests.
2. JavaScript Detections: Uncaught exceptions (with stack trace), browser console errors.
3. Navigation Detections: Navigation failure, unexpected blank page (HTTP 200 with 0 elements).
4. Finding Structure: id, title, category, severity, status (potential), confidence, evidence, recommendation.
5. Deduplication: Stable SHA-256 fingerprinting deduplicates identical issues and aggregates evidence occurrences.
6. Persistence: Database storage and retrieval of rich Finding models.
7. Real Browser Integration: End-to-end detection of real runtime exceptions and failed requests.
"""
from __future__ import annotations

import urllib.parse
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models import (
    ApplicationState,
    ConsoleMessage,
    FailedRequest,
    JavaScriptException,
    NetworkEvent,
    PlatformType,
    TestConfig,
    TestSession,
)
from app.detection.detector import Detector
from app.drivers.web.playwright.driver import WebTestDriver
from app.findings.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    compute_finding_fingerprint,
)
from app.storage.database import Base
from app.storage.db_models import FindingModel, TestModel
from app.storage.repository import TestRepository


# ---------------------------------------------------------------------------
# Database Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Unit Tests for Detectors
# ---------------------------------------------------------------------------


def test_detect_http_404_and_500():
    """Verify HTTP 404 and HTTP 500 detections with proper severities and status."""
    detector = Detector(test_id="test-123")

    state_404 = ApplicationState(
        url="https://example.com/missing-page",
        requested_url="https://example.com/missing-page",
        status_code=404,
        visible_text="404 Not Found",
    )
    findings_404 = detector.detect(state_404)
    assert len(findings_404) == 1
    f404 = findings_404[0]
    assert f404.category == FindingCategory.NETWORK
    assert f404.severity == FindingSeverity.MEDIUM
    assert f404.status == FindingStatus.POTENTIAL
    assert "404" in f404.title
    assert len(f404.evidence) == 1
    assert f404.evidence[0]["status_code"] == 404

    state_500 = ApplicationState(
        url="https://example.com/api/data",
        requested_url="https://example.com/api/data",
        status_code=500,
        visible_text="Internal Server Error",
    )
    findings_500 = detector.detect(state_500)
    assert len(findings_500) == 1
    f500 = findings_500[0]
    assert f500.category == FindingCategory.NETWORK
    assert f500.severity == FindingSeverity.CRITICAL  # main navigation 500 is critical
    assert f500.status == FindingStatus.POTENTIAL
    assert "500" in f500.title
    assert f500.confidence >= 0.9


def test_detect_failed_network_requests():
    """Verify failed network requests are detected and structured with evidence."""
    detector = Detector(test_id="test-123")

    state = ApplicationState(
        url="https://example.com",
        failed_requests=[
            FailedRequest(
                url="https://api.example.com/v1/telemetry",
                method="POST",
                failure_text="net::ERR_CONNECTION_REFUSED",
            )
        ],
    )

    findings = detector.detect(state)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.NETWORK
    assert f.severity == FindingSeverity.HIGH
    assert f.status == FindingStatus.POTENTIAL
    assert "ERR_CONNECTION_REFUSED" in f.description
    assert f.evidence[0]["failure_text"] == "net::ERR_CONNECTION_REFUSED"
    assert f.evidence[0]["method"] == "POST"


def test_detect_uncaught_js_exception():
    """Verify uncaught JavaScript runtime exceptions are detected with stack trace."""
    detector = Detector(test_id="test-123")

    state = ApplicationState(
        url="https://example.com/dashboard",
        js_exceptions=[
            JavaScriptException(
                message="TypeError: Cannot read properties of undefined (reading 'map')",
                stack="TypeError: Cannot read properties of undefined\n    at renderDashboard (app.js:42:15)",
            )
        ],
    )

    findings = detector.detect(state)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.JAVASCRIPT
    assert f.severity == FindingSeverity.HIGH
    assert f.status == FindingStatus.POTENTIAL
    assert "Cannot read properties of undefined" in f.title
    assert f.evidence[0]["stack"] is not None
    assert "renderDashboard" in f.evidence[0]["stack"]


def test_detect_console_errors():
    """Verify browser console errors are captured as findings."""
    detector = Detector(test_id="test-123")

    state = ApplicationState(
        url="https://example.com",
        console_messages=[
            ConsoleMessage(
                level="error",
                text="Failed to load resource: the server responded with a status of 403 (Forbidden)",
                location="bundle.js:100:12",
            ),
            ConsoleMessage(
                level="info",
                text="App initialized successfully",
            ),
        ],
    )

    findings = detector.detect(state)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.JAVASCRIPT
    assert f.severity == FindingSeverity.MEDIUM
    assert "403" in f.title or "403" in f.description
    assert f.evidence[0]["location"] == "bundle.js:100:12"


def test_detect_unexpected_blank_page():
    """Verify unexpected blank page (HTTP 200 with 0 elements and empty text) is detected."""
    detector = Detector(test_id="test-123")

    state = ApplicationState(
        url="https://example.com/app",
        status_code=200,
        elements=[],
        visible_text="",
    )

    findings = detector.detect(state)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.UI
    assert f.severity == FindingSeverity.HIGH
    assert "Blank Page" in f.title
    assert f.status == FindingStatus.POTENTIAL


def test_detect_navigation_failure():
    """Verify fatal navigation error detection."""
    detector = Detector(test_id="test-123")

    state = ApplicationState(
        url="",
        requested_url="https://invalid-non-existent-domain-xyz123.com",
        error="net::ERR_NAME_NOT_RESOLVED at https://invalid-non-existent-domain-xyz123.com",
    )

    findings = detector.detect(state)
    assert len(findings) == 1
    f = findings[0]
    assert f.category == FindingCategory.FUNCTIONAL
    assert f.severity == FindingSeverity.CRITICAL
    assert "Navigation Failure" in f.title


def test_fingerprint_deduplication_across_states():
    """Verify that repeated occurrences of the same issue do NOT generate duplicate findings."""
    detector = Detector(test_id="test-123")

    # Occurrence 1 on page 1
    state1 = ApplicationState(
        url="https://example.com/page1",
        js_exceptions=[
            JavaScriptException(
                message="ReferenceError: trackingCode is not defined",
                stack="ReferenceError: trackingCode is not defined\n    at index.html:10:5",
            )
        ],
    )
    findings1 = detector.detect(state1)
    assert len(findings1) == 1

    # Occurrence 2 on page 2 (same root error)
    state2 = ApplicationState(
        url="https://example.com/page1",
        js_exceptions=[
            JavaScriptException(
                message="ReferenceError: trackingCode is not defined",
                stack="ReferenceError: trackingCode is not defined\n    at index.html:10:5",
            )
        ],
    )
    findings2 = detector.detect(state2)
    # Deduplicated — no new finding returned
    assert len(findings2) == 0

    # Total findings in detector is still 1, but evidence has 2 occurrences
    all_findings = detector.all_findings
    assert len(all_findings) == 1
    assert len(all_findings[0].evidence) == 2


@pytest.mark.asyncio
async def test_finding_persistence_in_repository(test_db: AsyncSession):
    """Verify persisting and querying rich Finding models in TestRepository."""
    repo = TestRepository(test_db)

    # Create test
    test = TestModel(
        id="test-persist-01",
        url="https://example.com",
        status="running",
    )
    await repo.create(test)

    # Create and add finding
    finding_model = FindingModel(
        id="find-001",
        test_id="test-persist-01",
        severity="high",
        category="network",
        status="potential",
        confidence=0.92,
        title="HTTP 500 Internal Server Error",
        description="Backend API failed on /api/v1/orders",
        evidence=[
            {
                "type": "http_status_error",
                "status_code": 500,
                "url": "https://example.com/api/v1/orders",
            }
        ],
        reproduction={"action": "click", "selector": "#submit-order"},
        recommendation="Check database connection pool on API server.",
        fingerprint="sha256-abcdef1234567890",
    )
    await repo.add_finding(finding_model)

    # Query findings
    findings = await repo.get_findings("test-persist-01")
    assert len(findings) == 1
    persisted = findings[0]
    assert persisted.id == "find-001"
    assert persisted.severity == "high"
    assert persisted.category == "network"
    assert persisted.status == "potential"
    assert persisted.confidence == 0.92
    assert persisted.evidence[0]["status_code"] == 500
    assert persisted.reproduction["action"] == "click"
    assert persisted.recommendation == "Check database connection pool on API server."
    assert persisted.fingerprint == "sha256-abcdef1234567890"

    # Query by fingerprint
    fp_match = await repo.get_finding_by_fingerprint("test-persist-01", "sha256-abcdef1234567890")
    assert fp_match is not None
    assert fp_match.id == "find-001"


# ---------------------------------------------------------------------------
# Real Browser Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_browser_js_error_detection():
    """End-to-end test navigating a real browser page with script error and detecting finding."""
    session = TestSession(
        url="data:text/html,%3Chtml%3E%3Chead%3E%3Ctitle%3EBuggy%20App%3C%2Ftitle%3E%3Cscript%3EsetTimeout%28%28%29%20%3D%3E%20%7B%20throw%20new%20Error%28%27CRITICAL_UNCAUGHT_TEST_EXCEPTION%27%29%3B%20%7D%2C%2050%29%3C%2Fscript%3E%3C%2Fhead%3E%3Cbody%3E%3Ch1%3ETesting%20Errors%3C%2Fh1%3E%3C%2Fbody%3E%3C%2Fhtml%3E",
        platform=PlatformType.WEB,
        config=TestConfig(headless=True, navigation_timeout_ms=5000),
    )

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        state = await driver.navigate(session.url)

        # Allow async JS exception to fire
        import asyncio
        await asyncio.sleep(0.2)

        # Capture updated state
        state = await driver.get_current_state()

        detector = Detector(test_id=session.id)
        findings = detector.detect(state)

        assert len(findings) >= 1
        js_finding = next((f for f in findings if f.category == FindingCategory.JAVASCRIPT), None)
        assert js_finding is not None
        assert "CRITICAL_UNCAUGHT_TEST_EXCEPTION" in js_finding.description or "CRITICAL_UNCAUGHT_TEST_EXCEPTION" in js_finding.title
        assert js_finding.status == FindingStatus.POTENTIAL
        assert js_finding.confidence >= 0.9
    finally:
        await driver.close()

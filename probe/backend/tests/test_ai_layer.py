"""
Automated tests for PROBE AI Reasoning Layer (Step 07).

Tests:
1. Finding analysis Pydantic schema validation & serialization.
2. Fact vs Hypothesis vs Uncertainty separation.
3. Evidence distillation (filtering noise, avoiding bloated logs).
4. NullProvider fallback behavior when Gemini is unconfigured.
5. GeminiProvider error handling & graceful degradation (timeouts, rate limits, network errors).
6. API endpoints for single finding analysis and test-wide AI summary.
7. Database persistence of AI analysis and executive summary.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.ai.factory import get_ai_provider, set_ai_provider
from app.ai.prompts.finding_analysis import build_analysis_prompt, distill_finding_context
from app.ai.provider import AIProvider, AIRequest, AIResponse
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.null_provider import NullProvider
from app.ai.schemas.finding_analysis import (
    AIError,
    AIErrorType,
    FindingAnalysisResult,
    TestSummaryAnalysis,
)
from app.findings.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    compute_finding_fingerprint,
)
from app.main import app
from app.storage.database import Base, get_db
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
        poolclass=StaticPool,
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
# 1. Schema Validation & Fact/Hypothesis Separation
# ---------------------------------------------------------------------------


def test_finding_analysis_schema_validation():
    """Verify structured schema correctly enforces fields, defaults, and bounds."""
    result = FindingAnalysisResult(
        is_meaningful=True,
        category="javascript",
        severity_suggestion="high",
        confidence=0.95,
        observed_facts=[
            "HTTP 200 on /checkout",
            "Uncaught TypeError: Cannot read property 'total' of undefined",
        ],
        hypotheses=[
            "Cart state object is empty when navigating directly to checkout",
        ],
        uncertainty="Cannot inspect backend session storage without server logs",
        explanation="Checkout page crashes immediately upon loading if cart is uninitialized",
        possible_cause="Missing null check on cartItems.total in CheckoutSummary.tsx",
        recommendation="Guard total computation with optional chaining: cartItems?.total ?? 0",
        investigation_suggestion="Add test case for checkout with empty local storage",
        model_name="gemini-2.5-flash",
    )

    assert result.is_meaningful is True
    assert result.category == "javascript"
    assert result.severity_suggestion == "high"
    assert result.confidence == 0.95
    assert len(result.observed_facts) == 2
    assert len(result.hypotheses) == 1
    assert "Cannot inspect" in result.uncertainty

    # Verify JSON serialization & deserialization round-trip
    json_data = result.model_dump(mode="json")
    assert json_data["is_meaningful"] is True
    reloaded = FindingAnalysisResult.model_validate(json_data)
    assert reloaded.id == result.id
    assert reloaded.confidence == 0.95


# ---------------------------------------------------------------------------
# 2. Input Evidence Distillation Tests
# ---------------------------------------------------------------------------


def test_evidence_distillation_avoids_bloat():
    """Verify that huge raw telemetry is cleanly distilled into concise context."""
    finding = Finding(
        id="find-distill-01",
        test_id="test-01",
        title="JavaScript Exception: TypeError",
        category=FindingCategory.JAVASCRIPT,
        severity=FindingSeverity.HIGH,
        status=FindingStatus.POTENTIAL,
        confidence=0.88,
        description="Uncaught TypeError: x is undefined",
        evidence=[
            {"type": "js_exception", "message": "TypeError: x is undefined" + " " * 500, "url": "https://example.com/app"},
            {"type": "http_status_error", "status_code": 500, "url": "https://example.com/api/v1/data"},
        ] + [{"type": "noisy_beacon", "url": f"https://tracker.com/p?id={i}"} for i in range(50)],
        reproduction={
            "action_sequence": ['NAVIGATE("https://example.com/app")', "CLICK(#crash-btn)"],
            "status": "reproduced",
            "attempts": 1,
        },
    )

    distilled = distill_finding_context(finding)
    assert distilled["finding_id"] == "find-distill-01"
    assert distilled["category"] == "javascript"
    assert len(distilled["reproduction_sequence"]) == 2
    # Distillation should cap evidence items to prevent sending thousands of tokens
    assert len(distilled["evidence"]) <= 10
    # Messages should be truncated
    assert len(distilled["evidence"][0]["message"]) <= 300

    prompt = build_analysis_prompt(distilled)
    assert "find-distill-01" in prompt
    assert "CLICK(#crash-btn)" in prompt


# ---------------------------------------------------------------------------
# 3. NullProvider Fallback (When Gemini is Unconfigured / Offline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_provider_fallback():
    """Verify NullProvider returns safe deterministic analysis without crashing."""
    provider = NullProvider()
    assert provider.is_available is False
    assert provider.provider_name == "NullProvider"

    finding = Finding(
        id="find-null-01",
        test_id="test-01",
        title="HTTP 500 Internal Server Error",
        category=FindingCategory.NETWORK,
        severity=FindingSeverity.HIGH,
        status=FindingStatus.CONFIRMED,
        confidence=0.9,
        description="POST /api/checkout returned 500",
        evidence=[{"type": "http_response", "status_code": 500, "url": "https://example.com/api/checkout"}],
    )

    analysis = await provider.analyze_finding(finding)
    assert analysis.is_meaningful is True
    assert analysis.category == "network"
    assert analysis.severity_suggestion == "high"
    assert len(analysis.observed_facts) >= 1
    assert "Affected URL: https://example.com/api/checkout" in analysis.observed_facts
    assert analysis.error is not None
    assert analysis.error.error_type == AIErrorType.UNCONFIGURED

    # Summary
    summary = await provider.generate_test_summary([finding], {"id": "test-01"})
    assert summary.overall_health in ("degraded", "critical_issues_found")
    assert summary.error is not None


# ---------------------------------------------------------------------------
# 4. GeminiProvider Error Handling & Graceful Degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_provider_unconfigured_error():
    """Verify GeminiProvider without API key returns structured UNCONFIGURED error."""
    provider = GeminiProvider(api_key="", model_name="gemini-2.5-flash")
    assert provider.is_available is False

    finding = Finding(
        id="find-gem-01",
        test_id="test-01",
        title="Uncaught ReferenceError: foo is not defined",
        category=FindingCategory.JAVASCRIPT,
        severity=FindingSeverity.MEDIUM,
    )

    analysis = await provider.analyze_finding(finding)
    assert analysis.is_meaningful is True
    assert analysis.error is not None
    assert analysis.error.error_type == AIErrorType.UNCONFIGURED


@pytest.mark.asyncio
async def test_gemini_provider_timeout_handling():
    """Verify GeminiProvider handles timeouts gracefully without crashing."""
    provider = GeminiProvider(api_key="mock-api-key", model_name="gemini-2.5-flash")
    # Simulate client
    mock_client = MagicMock()

    def _slow_call(*args, **kwargs):
        import time
        time.sleep(2.0)

    mock_client.models.generate_content.side_effect = _slow_call
    provider._client = mock_client

    finding = Finding(
        id="find-gem-timeout",
        test_id="test-01",
        title="Navigation Failure",
        category=FindingCategory.FUNCTIONAL,
        severity=FindingSeverity.CRITICAL,
    )

    # Patch asyncio.wait_for timeout to 0.05s for quick test
    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        analysis = await provider.analyze_finding(finding)
        assert analysis.is_meaningful is True
        assert analysis.error is not None
        assert analysis.error.error_type == AIErrorType.TIMEOUT


@pytest.mark.asyncio
async def test_gemini_provider_quota_error_handling():
    """Verify rate limit / quota exceeded errors are classified into QUOTA_EXCEEDED."""
    provider = GeminiProvider(api_key="mock-api-key", model_name="gemini-2.5-flash")
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 ResourceExhausted: Quota exceeded for gemini-2.5-flash")
    provider._client = mock_client

    finding = Finding(
        id="find-gem-429",
        test_id="test-01",
        title="Network Error 404",
        category=FindingCategory.NETWORK,
        severity=FindingSeverity.LOW,
    )

    analysis = await provider.analyze_finding(finding)
    assert analysis.is_meaningful is True
    assert analysis.error is not None
    assert analysis.error.error_type == AIErrorType.QUOTA_EXCEEDED


# ---------------------------------------------------------------------------
# 5. Mock AI Provider for End-to-End API Integration
# ---------------------------------------------------------------------------


class MockAIProvider(AIProvider):
    """Predictable mock provider for API integration tests."""

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(content="Mock response", model="mock-gemini")

    async def analyze_finding(
        self,
        finding: Finding,
        evidence_context: Optional[dict[str, Any]] = None,
    ) -> FindingAnalysisResult:
        return FindingAnalysisResult(
            is_meaningful=True,
            category=finding.category.value if hasattr(finding.category, "value") else str(finding.category),
            severity_suggestion=finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
            confidence=0.94,
            observed_facts=[
                f"Observed finding: {finding.title}",
                "Replayable action sequence completed with matching error signature",
            ],
            hypotheses=[
                "Frontend event handler accessed uninitialized state property",
            ],
            uncertainty="Requires inspecting source bundle mapping",
            explanation=f"AI confirmed: {finding.description}",
            possible_cause="Uncaught error in button click handler",
            recommendation="Wrap the event handler in a try-catch block and add fallback UI",
            investigation_suggestion="Check browser console in DevTools while reproducing",
            model_name="mock-gemini-2.5-flash",
        )

    async def generate_test_summary(
        self,
        findings: list[Finding],
        test_summary: dict[str, Any],
    ) -> TestSummaryAnalysis:
        return TestSummaryAnalysis(
            overall_health="degraded" if findings else "healthy",
            key_takeaways=[f"Analyzed {len(findings)} findings."],
            top_risks=[f.title for f in findings],
            recommended_actions=["Prioritize critical UI exceptions."],
            model_name="mock-gemini-2.5-flash",
        )

    @property
    def provider_name(self) -> str:
        return "MockAIProvider"

    @property
    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# 6. REST API Endpoints & Persistence Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_analysis_api_endpoints_and_persistence(test_db: AsyncSession):
    """
    Test POST /api/tests/{test_id}/findings/{finding_id}/analyze and POST /api/tests/{test_id}/analyze.
    Verifies that AI analysis is properly computed, stored in SQLite, and returned via API.
    """
    repo = TestRepository(test_db)
    test_id = "test-ai-api-01"
    finding_id = "finding-ai-01"

    # Setup test and finding in DB
    test_model = TestModel(id=test_id, url="https://example.com/app", status="completed")
    await repo.create(test_model)

    finding_model = FindingModel(
        id=finding_id,
        test_id=test_id,
        severity="high",
        category="javascript",
        status="potential",
        confidence=0.85,
        title="JavaScript Exception: Cannot read property of undefined",
        description="Uncaught TypeError on button click",
        evidence=[{"type": "js_exception", "message": "TypeError: Cannot read property"}],
        reproduction={"action_sequence": ['NAVIGATE("https://example.com/app")', "CLICK(#btn)"]},
        fingerprint="fp-ai-api-123",
    )
    await repo.add_finding(finding_model)

    # Set mock AI provider
    set_ai_provider(MockAIProvider())

    from app.storage.database import get_db

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Analyze single finding
            resp = await client.post(f"/api/tests/{test_id}/findings/{finding_id}/analyze")
            assert resp.status_code == 200
            data = resp.json()

            assert data["is_meaningful"] is True
            assert data["category"] == "javascript"
            assert data["severity_suggestion"] == "high"
            assert data["confidence"] == 0.94
            assert len(data["observed_facts"]) >= 1
            assert len(data["hypotheses"]) >= 1
            assert data["recommendation"] != ""

            # 2. Verify finding persisted in DB with ai_analysis
            updated_finding = await repo.get_finding(finding_id)
            assert updated_finding is not None
            assert updated_finding.ai_analysis is not None
            assert updated_finding.ai_analysis["confidence"] == 0.94

            # 3. Retrieve finding via GET
            resp_get = await client.get(f"/api/tests/{test_id}/findings/{finding_id}")
            assert resp_get.status_code == 200
            f_data = resp_get.json()
            assert f_data["ai_analysis"] is not None
            assert f_data["ai_analysis"]["confidence"] == 0.94

            # 4. Generate test-wide AI summary
            resp_summary = await client.post(f"/api/tests/{test_id}/analyze")
            assert resp_summary.status_code == 200
            summary_data = resp_summary.json()
            assert summary_data["overall_health"] == "degraded"
            assert len(summary_data["key_takeaways"]) >= 1

            # 5. Verify test detail contains ai_summary
            resp_test = await client.get(f"/api/tests/{test_id}")
            assert resp_test.status_code == 200
            t_data = resp_test.json()
            assert t_data["ai_summary"] is not None
            assert t_data["ai_summary"]["overall_health"] == "degraded"

    finally:
        app.dependency_overrides.clear()
        set_ai_provider(None)

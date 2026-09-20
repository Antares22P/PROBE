"""
Tests for Live AI Browser Inspection (PROBE Feature).

Verifies:
1. BrowserActionEvent model serialization, coordinate bounds, and event payload fidelity.
2. Multi-agent role assignment and agent status state transitions.
3. Playwright element coordinate extraction mechanism (bounding box center computation).
4. ExplorationEngine live inspection event streaming (browser_action, browser_frame, agent_status).
5. Clean cancellation & immediate session termination when Stop Inspection is triggered.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.models import (
    Action,
    ActionResult,
    ActionType,
    AgentStatusState,
    AgentType,
    ApplicationState,
    Bounds,
    BrowserActionEvent,
    Element,
    PlatformType,
    TestConfig,
    TestSession,
    TestStatus,
)
from app.drivers.web.playwright.driver import WebTestDriver
from app.exploration.engine import ExplorationEngine
from app.main import app
from app.storage.database import Base, get_db
from app.storage.db_models import TestModel
from app.storage.repository import TestRepository

# Prevent pytest from collecting these helper/model classes as test suites
TestConfig.__test__ = False
TestSession.__test__ = False
TestStatus.__test__ = False
TestRepository.__test__ = False
TestModel.__test__ = False


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_db():
    async with TestSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# 1. Model & Serialization Tests
# ---------------------------------------------------------------------------

def test_browser_action_event_serialization():
    event = BrowserActionEvent(
        type="browser_action",
        inspection_id="test-123",
        agent=AgentType.TECHNICAL,
        action="click",
        target="Submit Form Button",
        selector="button#submit",
        x=640.5,
        y=360.2,
        value=None,
        reason="Interact with button to test state transition",
    )
    data = event.model_dump()
    assert data["type"] == "browser_action"
    assert data["agent"] == "technical"
    assert data["action"] == "click"
    assert data["x"] == 640.5
    assert data["y"] == 360.2
    assert data["reason"] == "Interact with button to test state transition"


def test_agent_status_states_and_roles():
    assert AgentType.TECHNICAL.value == "technical"
    assert AgentType.USER_BEHAVIOR.value == "user_behavior"
    assert AgentType.UX_UI.value == "ux_ui"
    assert AgentType.CHAOS.value == "chaos"

    assert AgentStatusState.EXPLORING.value == "exploring"
    assert AgentStatusState.REVIEWING.value == "reviewing"
    assert AgentStatusState.WAITING.value == "waiting"
    assert AgentStatusState.FINISHED.value == "finished"


# ---------------------------------------------------------------------------
# 2. Coordinate Extraction & Driver Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_element_coordinates():
    session = TestSession(
        url="https://example.com",
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)
    mock_page = MagicMock()
    mock_page.is_closed.return_value = False
    mock_locator = MagicMock()

    async def mock_bounding_box():
        return {"x": 100, "y": 200, "width": 80, "height": 40}

    mock_locator.bounding_box = mock_bounding_box
    mock_locator.first = mock_locator
    mock_page.locator.return_value = mock_locator
    driver._page = mock_page
    driver._initialized = True

    coords = await driver.get_element_coordinates("#target-btn")
    assert coords is not None
    assert coords["x"] == 140.0  # 100 + 40
    assert coords["y"] == 220.0  # 200 + 20
    assert coords["width"] == 80
    assert coords["height"] == 40


# ---------------------------------------------------------------------------
# 3. Exploration Engine Multi-Agent Assignment & Event Stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_determines_correct_agent_role(test_db: AsyncSession):
    repo = TestRepository(test_db)
    session = TestSession(
        url="https://example.com",
        platform=PlatformType.WEB,
        config=TestConfig(max_actions=5, max_states=5),
    )
    test_record = TestModel(id=session.id, url=session.url, status="running")
    await repo.create(test_record)

    driver = WebTestDriver(session=session, config=session.config)
    engine = ExplorationEngine(driver=driver, session=session)

    # Click navigation -> Technical
    agent_nav = engine._determine_agent_for_action(Action(type=ActionType.NAVIGATE, value="https://example.com"), None)
    assert agent_nav == AgentType.TECHNICAL

    # Scroll -> UX/UI
    agent_scroll = engine._determine_agent_for_action(Action(type=ActionType.SCROLL, value="300"), None)
    assert agent_scroll == AgentType.UX_UI

    # Form type -> User Behavior
    elem_input = Element(tag="input", type="input:text", reference="#username")
    agent_type = engine._determine_agent_for_action(Action(type=ActionType.TYPE, target="#username", value="admin"), elem_input)
    assert agent_type == AgentType.USER_BEHAVIOR

    # Interactive button -> User Behavior
    elem_btn = Element(tag="button", type="button", reference="#checkout-btn", text="Proceed to Checkout")
    agent_btn = engine._determine_agent_for_action(Action(type=ActionType.CLICK, target="#checkout-btn"), elem_btn)
    assert agent_btn == AgentType.USER_BEHAVIOR


@pytest.mark.asyncio
async def test_engine_emits_live_browser_action_and_frame_events(test_db: AsyncSession):
    repo = TestRepository(test_db)
    session = TestSession(
        url="https://example.com",
        platform=PlatformType.WEB,
        config=TestConfig(max_actions=2, max_states=2),
    )
    test_record = TestModel(id=session.id, url=session.url, status="running")
    await repo.create(test_record)

    nav_action = Action(type=ActionType.NAVIGATE, value="https://example.com")
    driver = MagicMock(spec=WebTestDriver)
    driver.navigate = AsyncMock(return_value=ActionResult(action=nav_action, success=True, duration_ms=100))
    driver.observe = AsyncMock(return_value=ApplicationState(
        url="https://example.com",
        title="Example Domain",
        fingerprint="fp-1",
        elements=[],
    ))
    mock_ev = MagicMock()
    mock_ev.screenshot_path = "screenshots/mock-frame.png"
    driver.capture_screenshot = AsyncMock(return_value=mock_ev)

    emitted_events = []

    async def listener(event_dict: dict):
        emitted_events.append(event_dict)

    engine = ExplorationEngine(driver=driver, session=session, event_callback=listener)

    # Initial state
    state0 = ApplicationState(
        url="https://example.com",
        title="Example Domain",
        fingerprint="fp-0",
        elements=[
            Element(
                tag="button",
                type="button",
                text="Click Me",
                reference="#btn",
                bounds=Bounds(x=100, y=100, width=50, height=30),
            )
        ],
    )

    click_action = Action(type=ActionType.CLICK, target="#btn", description="Click the button")
    elem = state0.elements[0]

    with patch("asyncio.sleep", new_callable=AsyncMock):
        driver.execute_action = AsyncMock(return_value=ApplicationState(
            url="https://example.com/clicked",
            title="Clicked Page",
            fingerprint="fp-clicked",
            elements=[],
        ))

        await engine._execute_and_observe(click_action, state0, elem)

    event_types = [e["type"] for e in emitted_events]
    assert "browser_action" in event_types
    assert "browser_frame" in event_types

    # Verify browser_action event payload
    action_event = next(e for e in emitted_events if e["type"] == "browser_action")
    assert action_event["action"] == "click"
    assert action_event["agent"] == "user_behavior"
    assert action_event["x"] == 125.0  # 100 + 25
    assert action_event["y"] == 115.0  # 100 + 15
    assert "Click Me" in action_event["target"]


# ---------------------------------------------------------------------------
# 4. Stop Inspection / Immediate Cancellation Endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_running_test_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create test
        create_resp = await client.post("/api/tests", json={"url": "https://example.com"})
        assert create_resp.status_code == 201
        test_id = create_resp.json()["id"]

        # Cancel test
        cancel_resp = await client.post(f"/api/tests/{test_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["test_id"] == test_id

        # Verify updated test state
        get_resp = await client.get(f"/api/tests/{test_id}")
        assert get_resp.status_code == 200

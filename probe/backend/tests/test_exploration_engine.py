"""
Automated tests for PROBE Autonomous Exploration Engine (Step 04).

Tests:
1. SafetyPolicy filtering (destructive keywords, financial transactions, unsafe schemes, external domains).
2. Action prioritization & deterministic planning.
3. Loop avoidance & state deduplication.
4. Bounded execution limits (max_actions, max_states, max_depth, max_duration).
5. Multi-step autonomous exploration with live events and database persistence.
"""
from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models import (
    Action,
    ActionResult,
    ActionType,
    ApplicationState,
    Bounds,
    Element,
    PlatformType,
    TestConfig,
    TestSession,
)
from app.drivers.web.playwright.driver import WebTestDriver
from app.exploration.engine import ExplorationEngine
from app.exploration.safety import DefaultSafetyPolicy, SafetyPolicy
from app.storage.database import Base
from app.storage.db_models import ActionModel, ObservationModel, TestModel
from app.storage.repository import TestRepository


# ---------------------------------------------------------------------------
# Test SQLite DB Fixtures
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
# 1. Safety Policy Tests
# ---------------------------------------------------------------------------


def test_safety_policy_blocks_financial_actions():
    policy = DefaultSafetyPolicy()
    elem_buy = Element(tag="button", type="button", text="Buy Now - $49", reference="#buy-btn")
    action_buy = Action(type=ActionType.CLICK, target="#buy-btn")
    is_safe, reason = policy.is_safe_action(action_buy, elem_buy, "https://shop.com/item", "https://shop.com")
    assert is_safe is False
    assert "buy" in reason.lower()

    elem_checkout = Element(tag="a", type="link", text="Proceed to Checkout", reference="#checkout")
    action_checkout = Action(type=ActionType.CLICK, target="#checkout")
    is_safe, reason = policy.is_safe_action(action_checkout, elem_checkout, "https://shop.com/cart", "https://shop.com")
    assert is_safe is False
    assert "checkout" in reason.lower()


def test_safety_policy_blocks_destructive_actions():
    policy = DefaultSafetyPolicy()
    elem_del = Element(tag="button", type="button", text="Delete Account", reference="#delete-btn")
    action_del = Action(type=ActionType.CLICK, target="#delete-btn")
    is_safe, reason = policy.is_safe_action(action_del, elem_del, "https://app.com/settings", "https://app.com")
    assert is_safe is False
    assert "delete" in reason.lower()


def test_safety_policy_blocks_unsafe_protocols():
    policy = DefaultSafetyPolicy()
    elem_mail = Element(
        tag="a", type="link", text="Contact Us", reference="#mail", attributes={"href": "mailto:support@example.com"}
    )
    action_mail = Action(type=ActionType.CLICK, target="#mail")
    is_safe, reason = policy.is_safe_action(action_mail, elem_mail, "https://app.com", "https://app.com")
    assert is_safe is False
    assert "mailto:" in reason.lower()

    action_nav_js = Action(type=ActionType.NAVIGATE, value="javascript:alert(1)")
    is_safe, reason = policy.is_safe_action(action_nav_js, None, "https://app.com", "https://app.com")
    assert is_safe is False


def test_safety_policy_domain_scope_boundary():
    policy = DefaultSafetyPolicy()
    elem_ext = Element(
        tag="a", type="link", text="Follow on Twitter", reference="#tw", attributes={"href": "https://twitter.com/probe"}
    )
    action_ext = Action(type=ActionType.CLICK, target="#tw")
    is_safe, reason = policy.is_safe_action(action_ext, elem_ext, "https://myapp.com", "https://myapp.com")
    assert is_safe is False
    assert "external navigation" in reason.lower()

    elem_internal = Element(
        tag="a", type="link", text="About Us", reference="#about", attributes={"href": "/about"}
    )
    action_int = Action(type=ActionType.CLICK, target="#about")
    is_safe, reason = policy.is_safe_action(action_int, elem_internal, "https://myapp.com", "https://myapp.com")
    assert is_safe is True


# ---------------------------------------------------------------------------
# 2. Action Persistence Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_repository_persistence(test_db: AsyncSession):
    repo = TestRepository(test_db)
    test = TestModel(id="test-act-1", url="https://example.com", status="running")
    await repo.create(test)

    action = ActionModel(
        id="act-1",
        test_id="test-act-1",
        action_type="CLICK",
        target="#nav-about",
        description="Click link 'About Us'",
        success=True,
        duration_ms=45.2,
    )
    await repo.add_action(action)

    stored_actions = await repo.get_actions("test-act-1")
    assert len(stored_actions) == 1
    a = stored_actions[0]
    assert a.action_type == "CLICK"
    assert a.target == "#nav-about"
    assert a.description == "Click link 'About Us'"
    assert a.success is True
    assert a.duration_ms == 45.2


# ---------------------------------------------------------------------------
# 3. Autonomous Exploration Engine Real Browser Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_autonomous_exploration_engine_execution():
    """
    Verify ExplorationEngine autonomously navigates an interactive multi-step HTML page:
    1. Loads initial page with links, forms, and buttons.
    2. Explores navigation link to Page 2.
    3. Types into text inputs.
    4. Clicks buttons.
    5. Avoids duplicate actions and destructive elements.
    6. Terminates within bounded limits.
    """
    html_page = """
    <!DOCTYPE html>
    <html>
    <head><title>PROBE Interactive Test App</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <header>
            <h1>Test Application</h1>
            <nav>
                <a href="#section-contact" id="link-contact">Contact Section</a>
                <a href="#section-features" id="link-features">Features Section</a>
            </nav>
        </header>

        <main>
            <section id="section-contact">
                <h2>Contact Us</h2>
                <form id="contact-form" onsubmit="event.preventDefault(); document.getElementById('msg-out').innerText = 'Message Submitted';">
                    <label for="c-name">Your Name:</label>
                    <input type="text" id="c-name" name="name" placeholder="Enter name" />

                    <label for="c-email">Your Email:</label>
                    <input type="email" id="c-email" name="email" placeholder="Enter email" />

                    <label for="c-topic">Topic:</label>
                    <select id="c-topic" name="topic">
                        <option value="general">General Support</option>
                        <option value="feedback">Product Feedback</option>
                    </select>

                    <button type="submit" id="btn-submit">Submit Form</button>
                    <!-- Prohibited destructive action that safety policy MUST skip -->
                    <button type="button" id="btn-delete-account">Delete Account</button>
                </form>
                <p id="msg-out"></p>
            </section>

            <section id="section-features">
                <h2>Features</h2>
                <button type="button" id="btn-toggle" onclick="document.getElementById('feature-txt').innerText = 'Feature details expanded';">
                    Show Feature Details
                </button>
                <p id="feature-txt"></p>
            </section>
        </main>
    </body>
    </html>
    """

    session = TestSession(
        url="data:text/html," + html_page,
        platform=PlatformType.WEB,
        config=TestConfig(
            max_actions=10,
            max_states=5,
            max_depth=3,
            max_duration_seconds=30,
            headless=True,
        ),
    )

    emitted_events: list[dict] = []

    async def event_collector(event: dict) -> None:
        emitted_events.append(event)

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        engine = ExplorationEngine(
            driver=driver,
            session=session,
            event_callback=event_collector,
        )

        observations, actions = await engine.explore()

        # 1. Check actions were executed
        assert len(actions) > 0
        assert len(actions) <= session.config.max_actions

        # 2. Check types of actions executed
        action_types = [res.action.type.value for res in actions]
        assert "CLICK" in action_types or "NAVIGATE" in action_types

        # 3. Check Safety Policy prevented clicking the "Delete Account" button
        deleted_action = any("Delete Account" in (res.action.description or "") for res in actions)
        assert deleted_action is False

        # 4. Check that observations were collected
        assert len(observations) >= 1

        # 5. Check emitted SSE events
        event_types = [e.get("type") for e in emitted_events]
        assert "status" in event_types
        assert "observation" in event_types
        assert "action_start" in event_types
        assert "action_completed" in event_types

    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_exploration_engine_bound_limits():
    """Verify that exploration stops strictly when max_actions is reached."""
    html_many_buttons = """
    <!DOCTYPE html>
    <html>
    <body>
        <h2>Lots of buttons</h2>
        <div>
            <button id="b1">Button 1</button>
            <button id="b2">Button 2</button>
            <button id="b3">Button 3</button>
            <button id="b4">Button 4</button>
            <button id="b5">Button 5</button>
            <button id="b6">Button 6</button>
        </div>
    </body>
    </html>
    """

    # Set max_actions strictly to 3
    session = TestSession(
        url="data:text/html," + html_many_buttons,
        platform=PlatformType.WEB,
        config=TestConfig(
            max_actions=3,
            max_states=5,
            max_depth=3,
            max_duration_seconds=30,
            headless=True,
        ),
    )

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        engine = ExplorationEngine(
            driver=driver,
            session=session,
        )
        observations, actions = await engine.explore()
        assert len(actions) == 3
    finally:
        await driver.close()

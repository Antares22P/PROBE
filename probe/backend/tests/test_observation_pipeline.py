"""
Automated tests for PROBE Deep Observation Pipeline.

Tests:
1. Interactive element discovery (links, buttons, inputs, selects, textareas, checkboxes, radios, forms)
2. Labels, ARIA attributes, bounding boxes, visibility, enabled state
3. Browser signals (console logs, JS errors, failed requests)
4. State fingerprint calculation and deduplication
5. ArtifactStorage abstraction (saving, retrieving screenshots and data)
6. Database persistence of deep observations
"""
from __future__ import annotations

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models import (
    ApplicationState,
    Bounds,
    ConsoleMessage,
    Dimensions,
    Element,
    FailedRequest,
    JavaScriptException,
    PlatformType,
    TestConfig,
    TestSession,
    Viewport,
    compute_state_fingerprint,
)
from app.drivers.web.playwright.driver import WebTestDriver
from app.exploration.explorer import Explorer
from app.main import app
from app.storage.artifacts import LocalArtifactStorage
from app.storage.database import Base, get_db
from app.storage.db_models import ObservationModel, TestModel
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
# 1. State Fingerprinting Tests
# ---------------------------------------------------------------------------


def test_state_fingerprint_determinism():
    """Verify state fingerprinting is deterministic and stable."""
    elements = [
        Element(id="1", tag="a", type="link", role="link", text="Home", reference="#home", label="Home Page"),
        Element(id="2", tag="button", type="button", role="button", text="Submit", reference="#btn", label="Submit Form"),
    ]
    fp1 = compute_state_fingerprint(
        url="https://example.com/login?b=2&a=1",
        title="Login Page",
        elements=elements,
        visible_text="Welcome to our login page",
    )
    fp2 = compute_state_fingerprint(
        url="https://example.com/login?a=1&b=2#section",
        title="Login Page",
        elements=list(reversed(elements)),  # reverse order to test sorting invariance
        visible_text="Welcome to our login page",
    )

    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex string


def test_state_fingerprint_sensitivity():
    """Verify different states produce different fingerprints."""
    elements1 = [Element(tag="button", type="button", text="Click me", reference="#btn")]
    elements2 = [Element(tag="button", type="button", text="Different text", reference="#btn")]

    fp1 = compute_state_fingerprint("https://example.com", "Title A", elements1, "Text A")
    fp2 = compute_state_fingerprint("https://example.com", "Title A", elements2, "Text A")
    fp3 = compute_state_fingerprint("https://example.com", "Title B", elements1, "Text A")
    fp4 = compute_state_fingerprint("https://other.com", "Title A", elements1, "Text A")

    assert fp1 != fp2
    assert fp1 != fp3
    assert fp1 != fp4


# ---------------------------------------------------------------------------
# 2. Artifact Storage Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_artifact_storage():
    """Verify saving and retrieving screenshots and data via ArtifactStorage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalArtifactStorage(base_dir=tmpdir)
        test_id = "test-session-123"
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        path = await storage.save_screenshot(test_id, dummy_png, name="custom_screen.png")
        assert os.path.exists(path)
        assert path.endswith("custom_screen.png")

        retrieved = await storage.get_screenshot(path)
        assert retrieved == dummy_png

        # Test relative path retrieval
        rel_path = os.path.relpath(path, tmpdir)
        retrieved_rel = await storage.get_screenshot(rel_path)
        assert retrieved_rel == dummy_png

        # Test arbitrary data saving
        data_path = await storage.save_data(test_id, "test log content", "log.txt")
        assert os.path.exists(data_path)
        retrieved_data = await storage.get_data(data_path)
        assert retrieved_data == b"test log content"


# ---------------------------------------------------------------------------
# 3. Database Persistence Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_observation_repository_persistence(test_db: AsyncSession):
    """Verify that full observation state, signals, and fingerprints persist to SQLite."""
    repo = TestRepository(test_db)

    test = TestModel(id="test-1", url="https://example.com", status="running")
    await repo.create(test)

    obs = ObservationModel(
        test_id="test-1",
        url="https://example.com/app",
        requested_url="https://example.com",
        title="Test App",
        visible_text="Hello World",
        viewport={"width": 1280, "height": 720},
        page_dimensions={"width": 1280.0, "height": 2400.0},
        status_code=200,
        duration_ms=350.5,
        element_count=3,
        elements_data=[
            {"id": "e1", "type": "link", "text": "Home", "reference": "#home"},
            {"id": "e2", "type": "button", "text": "Save", "reference": "#save"},
        ],
        console_messages=[{"level": "log", "text": "Application loaded"}],
        console_errors=["[error] Failed to load resource"],
        js_exceptions=[{"message": "Uncaught TypeError", "stack": "at app.js:10"}],
        failed_requests=[{"url": "https://example.com/api/fail", "method": "GET", "failure_text": "404 Not Found"}],
        fingerprint="a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890",
    )
    await repo.add_observation(obs)

    # Query back
    stored_obs = await repo.get_observations("test-1")
    assert len(stored_obs) == 1
    o = stored_obs[0]
    assert o.url == "https://example.com/app"
    assert o.visible_text == "Hello World"
    assert o.viewport == {"width": 1280, "height": 720}
    assert o.page_dimensions == {"width": 1280.0, "height": 2400.0}
    assert o.fingerprint == "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890"
    assert len(o.elements_data) == 2
    assert len(o.console_messages) == 1
    assert len(o.js_exceptions) == 1
    assert len(o.failed_requests) == 1

    # Query by fingerprint
    by_fp = await repo.get_observation_by_fingerprint("test-1", o.fingerprint)
    assert by_fp is not None
    assert by_fp.id == o.id


# ---------------------------------------------------------------------------
# 4. Deep Browser Observation End-to-End Tests with Playwright
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deep_element_discovery_in_browser():
    """
    Test that WebTestDriver extracts:
    - links, buttons, inputs (text, password, email, checkbox, radio), textareas, selects, forms
    - labels, ARIA roles, visible & enabled states, bounding boxes
    - page dimensions and visible text
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Observation Test Page</title></head>
    <body style="margin:0; padding:20px; font-family:sans-serif;">
        <h1>PROBE Test Form</h1>
        <p>This is visible page text for testing.</p>

        <a href="https://example.com/docs" id="docs-link" aria-label="Documentation Page">Documentation</a>

        <form id="login-form" action="/submit" method="POST">
            <label for="username">Username:</label>
            <input type="text" id="username" name="user_name" placeholder="Enter username" />

            <label for="password">Password:</label>
            <input type="password" id="password" name="user_pass" />

            <label>
                <input type="checkbox" id="remember-me" name="remember" checked />
                Remember Me
            </label>

            <fieldset>
                <legend>Role</legend>
                <label><input type="radio" name="role" value="admin" id="role-admin" /> Admin</label>
                <label><input type="radio" name="role" value="user" id="role-user" checked /> User</label>
            </fieldset>

            <label for="bio">Bio:</label>
            <textarea id="bio" name="bio_text" placeholder="Tell us about yourself"></textarea>

            <label for="country">Country:</label>
            <select id="country" name="country">
                <option value="us">United States</option>
                <option value="uk">United Kingdom</option>
            </select>

            <button type="submit" id="submit-btn">Sign In</button>
            <button type="button" id="disabled-btn" disabled>Disabled Action</button>
        </form>

        <div role="button" id="custom-btn" tabindex="0" aria-label="Custom Action">Custom Clickable</div>
        <div style="display:none;"><button id="hidden-btn">Hidden</button></div>
    </body>
    </html>
    """

    session = TestSession(
        url="data:text/html," + html_content,
        platform=PlatformType.WEB,
        config=TestConfig(headless=True, viewport_width=1280, viewport_height=720),
    )

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        state = await driver.navigate(session.url)

        assert state.title == "Observation Test Page"
        assert "This is visible page text for testing" in state.visible_text
        assert state.viewport is not None
        assert state.viewport.width == 1280
        assert state.viewport.height == 720
        assert state.page_dimensions is not None
        assert state.page_dimensions.width >= 1280
        assert state.page_dimensions.height >= 720
        assert state.fingerprint is not None
        assert len(state.fingerprint) == 64

        # Check discovered elements
        elem_map = {e.id: e for e in state.elements if e.id}

        # Link
        assert "docs-link" in elem_map
        link = elem_map["docs-link"]
        assert link.type == "link"
        assert link.text == "Documentation"
        assert "Documentation" in link.label
        assert link.visible is True

        # Input text with label
        assert "username" in elem_map
        username = elem_map["username"]
        assert username.type == "input:text"
        assert "Username" in username.label or username.label == "Enter username"
        assert username.visible is True
        assert username.enabled is True

        # Input password
        assert "password" in elem_map
        pwd = elem_map["password"]
        assert pwd.type == "input:password"
        assert pwd.visible is True

        # Checkbox
        assert "remember-me" in elem_map
        chk = elem_map["remember-me"]
        assert chk.type == "checkbox"

        # Radio
        assert "role-admin" in elem_map
        assert elem_map["role-admin"].type == "radio"

        # Textarea
        assert "bio" in elem_map
        bio = elem_map["bio"]
        assert bio.type == "textarea"

        # Select
        assert "country" in elem_map
        country = elem_map["country"]
        assert country.type == "select"

        # Buttons
        assert "submit-btn" in elem_map
        btn = elem_map["submit-btn"]
        assert btn.type == "button"
        assert btn.text == "Sign In"
        assert btn.enabled is True

        assert "disabled-btn" in elem_map
        dis_btn = elem_map["disabled-btn"]
        assert dis_btn.enabled is False

        # Role button
        assert "custom-btn" in elem_map
        c_btn = elem_map["custom-btn"]
        assert c_btn.role == "button"
        assert c_btn.label == "Custom Action"

        # Hidden element
        assert "hidden-btn" in elem_map
        assert elem_map["hidden-btn"].visible is False

    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_browser_signals_capture():
    """
    Test that WebTestDriver captures:
    - console.log, console.warn, console.error
    - uncaught JavaScript exceptions
    """
    html_signals = """
    <!DOCTYPE html>
    <html>
    <head><title>Signals Test</title></head>
    <body>
        <h2>Browser Signals Testing</h2>
        <script>
            console.log("Informational message from app");
            console.warn("Warning: Deprecated API called");
            console.error("Critical error in renderer");
            setTimeout(() => {
                throw new Error("Uncaught async exception in test");
            }, 50);
        </script>
    </body>
    </html>
    """

    session = TestSession(
        url="data:text/html," + html_signals,
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )

    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        state = await driver.navigate(session.url)
        # Give page script time to fire timeout
        import asyncio
        await asyncio.sleep(0.15)
        # Re-capture current state to collect late errors
        state = await driver.get_current_state()

        # Check console messages
        msg_texts = [m.text for m in state.console_messages]
        assert any("Informational message from app" in t for t in msg_texts)
        assert any("Warning: Deprecated API called" in t for t in msg_texts)
        assert any("Critical error in renderer" in t for t in msg_texts)

        # Check console errors
        assert len(state.console_errors) >= 2

        # Check uncaught JS exception
        assert len(state.js_exceptions) >= 1
        assert any("Uncaught async exception in test" in ex.message for ex in state.js_exceptions)

    finally:
        await driver.close()


@pytest.mark.asyncio
async def test_explorer_deduplication():
    """Verify Explorer tracks visited state fingerprints and prevents redundant processing."""
    session = TestSession(
        url="data:text/html,<h1>Page 1</h1>",
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)
    try:
        await driver.initialize()
        explorer = Explorer(driver=driver, session=session)

        states = await explorer.explore_page(session.url)
        assert len(states) == 1
        fp = states[0].fingerprint
        assert fp is not None

        assert explorer.is_state_visited(fp) is True
        assert fp in explorer.visited_fingerprints
        assert len(explorer.visited_urls) == 1

    finally:
        await driver.close()

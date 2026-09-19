"""
Test that WebTestDriver can initialize Playwright without error.
"""
import pytest

from app.core.models import PlatformType, TestConfig, TestSession
from app.drivers.web.playwright.driver import WebTestDriver


@pytest.mark.asyncio
async def test_web_driver_initialize_and_close():
    """WebTestDriver must start Chromium and close cleanly."""
    session = TestSession(
        url="https://example.com",
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)

    assert not driver.is_initialized

    await driver.initialize()
    assert driver.is_initialized

    await driver.close()
    assert not driver.is_initialized


@pytest.mark.asyncio
async def test_web_driver_navigate():
    """WebTestDriver must navigate to a URL and return ApplicationState."""
    session = TestSession(
        url="https://example.com",
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)

    try:
        await driver.initialize()
        state = await driver.navigate("https://example.com")
        assert state.url != ""
        assert "example" in state.url.lower() or "example" in state.title.lower()
    finally:
        await driver.close()

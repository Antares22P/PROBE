"""
Test that WebTestDriver can initialize Playwright, navigate, and capture state.
"""
import pytest

from app.core.models import PlatformType, TestConfig, TestSession
from app.drivers.web.playwright.driver import WebTestDriver

TEST_PAGE = "data:text/html,%3Chtml%3E%3Chead%3E%3Ctitle%3EWebTestDriver%20Test%3C/title%3E%3C/head%3E%3Cbody%3E%3Ch1%3EHello%3C/h1%3E%3C/body%3E%3C/html%3E"


@pytest.mark.asyncio
async def test_web_driver_initialize_and_close():
    """WebTestDriver must start Chromium and close cleanly."""
    session = TestSession(
        url=TEST_PAGE,
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)

    assert not driver.is_initialized

    await driver.initialize()
    assert driver.is_initialized
    assert driver.is_initialized is True

    await driver.close()
    assert not driver.is_initialized


@pytest.mark.asyncio
async def test_web_driver_navigate():
    """WebTestDriver must navigate to a URL and return ApplicationState."""
    session = TestSession(
        url=TEST_PAGE,
        platform=PlatformType.WEB,
        config=TestConfig(headless=True),
    )
    driver = WebTestDriver(session=session, config=session.config)

    try:
        await driver.initialize()
        state = await driver.navigate(TEST_PAGE)
        assert state.url != ""
        assert state.title == "WebTestDriver Test"
        assert state.duration_ms is not None
    finally:
        await driver.close()

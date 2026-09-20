"""
Explorer — autonomous page exploration logic.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.models import Action, ActionType, ApplicationState, TestSession
from app.drivers.common.base import TestDriver
from app.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class Explorer:
    """
    Explores a web application autonomously.

    Uses a TestDriver (platform-neutral) to navigate and interact.
    Does NOT import Playwright directly.
    """

    def __init__(self, driver: TestDriver, session: TestSession) -> None:
        self._driver = driver
        self._session = session
        self._visited_urls: set[str] = set()
        self._visited_fingerprints: set[str] = set()

    async def explore_page(self, url: str) -> list[ApplicationState]:
        """Navigate to a URL, capture screenshot, and collect deep application state."""
        logger.info(
            "explore_navigate",
            component="explorer",
            test_id=self._session.id,
            url=url,
        )

        states: list[ApplicationState] = []

        navigate_action = Action(type=ActionType.NAVIGATE, value=url)
        state = await self._driver.execute_action(navigate_action)

        # Capture screenshot for the navigated page (if not fatal error)
        try:
            evidence = await self._driver.capture_screenshot()
            state.screenshot_path = evidence.screenshot_path
        except Exception as exc:
            logger.warning(
                "explore_screenshot_failed",
                component="explorer",
                test_id=self._session.id,
                error=str(exc),
            )

        states.append(state)
        if state.url:
            self._visited_urls.add(state.url)
        if state.fingerprint:
            self._visited_fingerprints.add(state.fingerprint)

        logger.info(
            "page_captured",
            component="explorer",
            test_id=self._session.id,
            url=state.url,
            status_code=state.status_code,
            duration_ms=state.duration_ms,
            element_count=len(state.elements),
            fingerprint=state.fingerprint,
            screenshot_path=state.screenshot_path,
        )

        return states

    def is_state_visited(self, fingerprint: str) -> bool:
        """Check if a state fingerprint has already been discovered in this session."""
        return fingerprint in self._visited_fingerprints

    @property
    def visited_urls(self) -> set[str]:
        return set(self._visited_urls)

    @property
    def visited_fingerprints(self) -> set[str]:
        return set(self._visited_fingerprints)


"""
Explorer — autonomous page exploration logic.

Explores a web application by navigating links and interacting
with interactive elements, collecting observations along the way.
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

    async def explore_page(self, url: str) -> list[ApplicationState]:
        """
        Navigate to a URL and collect the initial application state.
        Returns a list of observed states.
        """
        logger.info(
            "exploring_page",
            component="explorer",
            event="navigate",
            test_id=self._session.id,
            url=url,
        )

        states: list[ApplicationState] = []

        navigate_action = Action(type=ActionType.NAVIGATE, value=url)
        state = await self._driver.execute_action(navigate_action)
        states.append(state)
        self._visited_urls.add(state.url)

        # Capture a screenshot as evidence
        await self._driver.capture_screenshot()

        logger.info(
            "page_explored",
            component="explorer",
            event="page_captured",
            test_id=self._session.id,
            url=state.url,
            element_count=len(state.elements),
        )

        return states

    @property
    def visited_urls(self) -> set[str]:
        return set(self._visited_urls)

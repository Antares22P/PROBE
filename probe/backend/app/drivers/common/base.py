"""
TestDriver — platform-neutral abstract base class.

PROBE Core imports ONLY this interface. Platform-specific drivers
(WebTestDriver, AndroidTestDriver, IOSTestDriver) implement it.

IMPORTANT: This module MUST NOT import Playwright, Appium, or any
platform-specific library.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.core.models import (
    Action,
    ApplicationState,
    Evidence,
    NetworkEvent,
    TestConfig,
    TestSession,
)


class TestDriver(ABC):
    """
    Abstract interface for all platform test drivers.

    Implementations:
        - WebTestDriver  (probe.backend.app.drivers.web.playwright.driver)
        - AndroidTestDriver  (future — probe.backend.app.drivers.mobile.android.driver)
        - IOSTestDriver      (future — probe.backend.app.drivers.mobile.ios.driver)
    """

    def __init__(self, session: TestSession, config: TestConfig) -> None:
        self._session = session
        self._config = config
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the driver (launch browser, connect to device, etc.)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release all resources held by the driver."""
        ...

    @abstractmethod
    async def reset_state(self) -> None:
        """Reset to a clean state (clear cookies, reload, etc.)."""
        ...

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @abstractmethod
    async def navigate(self, url: str) -> ApplicationState:
        """Navigate to a URL and return the resulting application state."""
        ...

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_current_state(self) -> ApplicationState:
        """Capture and return the current application state."""
        ...

    @abstractmethod
    async def get_interactive_elements(self) -> list:
        """Return a list of interactive Elements on the current screen."""
        ...

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute_action(self, action: Action) -> ApplicationState:
        """
        Execute a single action and return the resulting application state.

        Implementations must handle all ActionType values they support and
        raise DriverError for unsupported or failed actions.
        """
        ...

    # ------------------------------------------------------------------
    # Evidence Collection
    # ------------------------------------------------------------------

    @abstractmethod
    async def capture_screenshot(self, path: Optional[str] = None) -> Evidence:
        """Capture a screenshot and return Evidence."""
        ...

    @abstractmethod
    async def collect_logs(self) -> list[str]:
        """Collect console/system logs from the current session."""
        ...

    @abstractmethod
    async def collect_network_events(self) -> list[NetworkEvent]:
        """Return captured network events from the current session."""
        ...

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def session(self) -> TestSession:
        return self._session

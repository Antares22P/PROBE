"""
AndroidTestDriver — stub for future implementation.

This module is an extension point. Do NOT implement mobile testing here.
The full implementation will use Appium / ADB.

All reusable PROBE components (Core, Actions, State, Observations,
Findings, Reproduction, AI, Storage) work without modification.
"""
from __future__ import annotations

from typing import Optional

from app.core.models import (
    Action,
    ApplicationState,
    Evidence,
    NetworkEvent,
    TestConfig,
    TestSession,
)
from app.drivers.common.base import TestDriver
from app.utils.errors import DriverError


class AndroidTestDriver(TestDriver):
    """
    Future Android test driver using Appium / ADB.

    NOT IMPLEMENTED. Raises DriverError on all calls.
    """

    def __init__(self, session: TestSession, config: TestConfig) -> None:
        super().__init__(session, config)

    async def initialize(self) -> None:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def close(self) -> None:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def reset_state(self) -> None:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def navigate(self, url: str) -> ApplicationState:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def get_current_state(self) -> ApplicationState:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def get_interactive_elements(self) -> list:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def execute_action(self, action: Action) -> ApplicationState:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def capture_screenshot(self, path: Optional[str] = None) -> Evidence:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def collect_logs(self) -> list[str]:
        raise DriverError("AndroidTestDriver is not implemented in V1")

    async def collect_network_events(self) -> list[NetworkEvent]:
        raise DriverError("AndroidTestDriver is not implemented in V1")

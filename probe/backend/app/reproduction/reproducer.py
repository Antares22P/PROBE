"""
Reproducer — attempts to reproduce detected findings.
"""
from __future__ import annotations

from app.core.models import Action, ActionType, TestSession
from app.drivers.common.base import TestDriver
from app.findings.models import Finding
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Reproducer:
    """Attempts to reproduce a finding by replaying actions."""

    def __init__(self, driver: TestDriver, session: TestSession) -> None:
        self._driver = driver
        self._session = session

    async def reproduce(self, finding: Finding, steps: list[Action]) -> bool:
        """
        Attempt to reproduce a finding by executing the given steps.

        Returns True if the finding was reproduced, False otherwise.
        """
        logger.info(
            "reproducing_finding",
            component="reproducer",
            event="start",
            test_id=self._session.id,
            finding_id=finding.id,
        )

        try:
            for action in steps:
                await self._driver.execute_action(action)

            state = await self._driver.get_current_state()

            # Simple heuristic: check if similar errors exist
            if finding.category == "console_error":
                reproduced = any(finding.description in err for err in state.console_errors)
            elif finding.category == "network_error":
                reproduced = any(
                    str(evt.status) in finding.title
                    for evt in state.network_events
                    if evt.status is not None
                )
            else:
                reproduced = False

            logger.info(
                "reproduction_result",
                component="reproducer",
                event="complete",
                test_id=self._session.id,
                finding_id=finding.id,
                reproduced=reproduced,
            )
            return reproduced

        except Exception as exc:
            logger.warning(
                "reproduction_failed",
                component="reproducer",
                event="error",
                test_id=self._session.id,
                finding_id=finding.id,
                error=str(exc),
            )
            return False

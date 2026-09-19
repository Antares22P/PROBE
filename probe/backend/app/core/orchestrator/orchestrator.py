"""
Orchestrator — drives the full PROBE test lifecycle.

Coordinates: Explorer → Detector → DecisionMaker → Reproducer → AIProvider.

PROBE Core does NOT import Playwright. It only uses TestDriver (the ABC).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Callable, Coroutine, Any, Optional

from app.ai.providers.null_provider import NullProvider
from app.core.models import ApplicationState, TestSession, TestStatus
from app.decisions.decision_maker import DecisionMaker
from app.detection.detector import Detector
from app.drivers.common.base import TestDriver
from app.exploration.explorer import Explorer
from app.findings.models import Finding
from app.reproduction.reproducer import Reproducer
from app.storage.db_models import FindingModel, ObservationModel
from app.storage.repository import TestRepository
from app.utils.errors import DriverError, InternalError
from app.utils.logging import get_logger, bind_test_id, clear_context

logger = get_logger(__name__)

# SSE event callback type
EventCallback = Callable[[dict], Coroutine[Any, Any, None]]


class Orchestrator:
    """
    Drives the entire test lifecycle.

    Usage:
        orch = Orchestrator(driver, session, repository)
        await orch.run(event_callback)
    """

    def __init__(
        self,
        driver: TestDriver,
        session: TestSession,
        repository: TestRepository,
        event_callback: Optional[EventCallback] = None,
    ) -> None:
        self._driver = driver
        self._session = session
        self._repo = repository
        self._event_callback = event_callback
        self._ai = NullProvider()

    async def run(self) -> None:
        """Execute the full test and persist results."""
        bind_test_id(self._session.id)
        logger.info(
            "test_starting",
            component="orchestrator",
            event="run_start",
            test_id=self._session.id,
            url=self._session.url,
        )

        await self._emit("status", {"status": "running", "message": "Initializing driver..."})

        try:
            await self._driver.initialize()
            await self._repo.update_status(self._session.id, "running")

            # Exploration
            await self._emit("status", {"status": "running", "message": "Exploring application..."})
            explorer = Explorer(self._driver, self._session)
            states = await explorer.explore_page(self._session.url)

            # Detection + Observation persistence
            detector = Detector(self._session.id)
            all_findings: list[Finding] = []

            for state in states:
                obs = ObservationModel(
                    test_id=self._session.id,
                    url=state.url,
                    title=state.title,
                    element_count=len(state.elements),
                    console_errors=state.console_errors,
                )
                await self._repo.add_observation(obs)
                await self._emit("observation", {
                    "url": state.url,
                    "title": state.title,
                    "element_count": len(state.elements),
                    "console_errors": len(state.console_errors),
                })

                findings = detector.detect(state)
                all_findings.extend(findings)

                for finding in findings:
                    finding_model = FindingModel(
                        test_id=self._session.id,
                        severity=finding.severity.value,
                        category=finding.category,
                        title=finding.title,
                        description=finding.description,
                    )
                    await self._repo.add_finding(finding_model)
                    await self._emit("finding", {
                        "severity": finding.severity.value,
                        "category": finding.category,
                        "title": finding.title,
                        "description": finding.description,
                    })

            # AI analysis (no-op in V1)
            await self._emit("status", {"status": "running", "message": "Analyzing findings..."})
            ai_summary = await self._ai.analyze_findings(
                [f.model_dump() for f in all_findings],
                {"url": self._session.url},
            )

            # Complete
            await self._repo.update_status(self._session.id, "completed")
            await self._emit("status", {
                "status": "completed",
                "message": "Test completed.",
                "findings_count": len(all_findings),
                "ai_summary": ai_summary,
            })

            logger.info(
                "test_completed",
                component="orchestrator",
                event="run_complete",
                test_id=self._session.id,
                findings=len(all_findings),
            )

        except DriverError as exc:
            logger.error(
                "test_driver_error",
                component="orchestrator",
                event="driver_error",
                test_id=self._session.id,
                error=str(exc),
            )
            await self._repo.update_status(self._session.id, "failed", str(exc))
            await self._emit("status", {"status": "failed", "message": str(exc)})

        except Exception as exc:
            logger.error(
                "test_internal_error",
                component="orchestrator",
                event="internal_error",
                test_id=self._session.id,
                error=str(exc),
            )
            await self._repo.update_status(self._session.id, "failed", "Internal error occurred")
            await self._emit("status", {"status": "failed", "message": "Internal error occurred"})

        finally:
            try:
                await self._driver.close()
            except Exception:
                pass
            clear_context()

    async def _emit(self, event_type: str, data: dict) -> None:
        """Send an SSE event if a callback is registered."""
        if self._event_callback:
            try:
                await self._event_callback({"type": event_type, **data})
            except Exception as exc:
                logger.warning(
                    "event_emit_failed",
                    component="orchestrator",
                    error=str(exc),
                )

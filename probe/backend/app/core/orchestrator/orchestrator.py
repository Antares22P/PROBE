"""
Orchestrator — drives the full PROBE test lifecycle.
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
from app.storage.db_models import EvidenceModel, FindingModel, ObservationModel
from app.storage.repository import TestRepository
from app.utils.errors import DriverError, InternalError
from app.utils.logging import get_logger, bind_test_id, clear_context

logger = get_logger(__name__)

EventCallback = Callable[[dict], Coroutine[Any, Any, None]]


class Orchestrator:
    """
    Drives the entire test lifecycle.

    Usage:
        orch = Orchestrator(driver, session, repository)
        await orch.run()
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
            test_id=self._session.id,
            url=self._session.url,
        )

        await self._emit("status", {"status": "running", "message": "Launching Chromium browser..."})

        try:
            await self._driver.initialize()
            await self._repo.update_status(self._session.id, "running")

            await self._emit("status", {
                "status": "running",
                "message": f"Navigating to {self._session.url} in isolated context...",
            })

            explorer = Explorer(self._driver, self._session)
            states = await explorer.explore_page(self._session.url)

            detector = Detector(self._session.id)
            all_findings: list[Finding] = []
            latest_state: Optional[ApplicationState] = None

            for state in states:
                latest_state = state

                # Persist observation with complete telemetry
                obs = ObservationModel(
                    test_id=self._session.id,
                    url=state.url,
                    requested_url=state.requested_url or self._session.url,
                    title=state.title,
                    visible_text=state.visible_text,
                    viewport=state.viewport.model_dump() if state.viewport else {},
                    page_dimensions=state.page_dimensions.model_dump() if state.page_dimensions else {},
                    status_code=state.status_code,
                    duration_ms=state.duration_ms,
                    error=state.error,
                    screenshot_path=state.screenshot_path,
                    element_count=len(state.elements),
                    elements_data=[e.model_dump() for e in state.elements],
                    console_messages=[c.model_dump(mode="json") for c in state.console_messages],
                    console_errors=state.console_errors,
                    js_exceptions=[j.model_dump(mode="json") for j in state.js_exceptions],
                    failed_requests=[f.model_dump(mode="json") for f in state.failed_requests],
                    network_events=[n.model_dump(mode="json") for n in state.network_events],
                    fingerprint=state.fingerprint,
                )
                await self._repo.add_observation(obs)

                # Persist screenshot evidence if present
                if state.screenshot_path:
                    ev = EvidenceModel(
                        test_id=self._session.id,
                        evidence_type="screenshot",
                        screenshot_path=state.screenshot_path,
                    )
                    await self._repo.add_evidence(ev)

                # Broadcast observation event with full telemetry
                await self._emit("observation", {
                    "requested_url": state.requested_url or self._session.url,
                    "url": state.url,
                    "title": state.title,
                    "status_code": state.status_code,
                    "duration_ms": state.duration_ms,
                    "error": state.error,
                    "element_count": len(state.elements),
                    "elements": [e.model_dump() for e in state.elements],
                    "console_messages": [c.model_dump(mode="json") for c in state.console_messages],
                    "console_errors": state.console_errors,
                    "js_exceptions": [j.model_dump(mode="json") for j in state.js_exceptions],
                    "failed_requests": [f.model_dump(mode="json") for f in state.failed_requests],
                    "viewport": state.viewport.model_dump() if state.viewport else None,
                    "page_dimensions": state.page_dimensions.model_dump() if state.page_dimensions else None,
                    "fingerprint": state.fingerprint,
                    "screenshot_url": f"/api/tests/{self._session.id}/screenshot" if state.screenshot_path else None,
                })

                if state.screenshot_path:
                    await self._emit("screenshot", {
                        "url": f"/api/tests/{self._session.id}/screenshot",
                        "path": state.screenshot_path,
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

            await self._emit("status", {"status": "running", "message": "Analyzing findings..."})
            ai_summary = await self._ai.analyze_findings(
                [f.model_dump() for f in all_findings],
                {"url": self._session.url},
            )

            # Determine final status (completed vs failed if navigation had fatal error)
            final_status = "completed"
            err_msg: Optional[str] = None
            if latest_state and latest_state.error and not latest_state.url:
                final_status = "failed"
                err_msg = latest_state.error

            await self._repo.update_status(self._session.id, final_status, error_message=err_msg)
            await self._emit("status", {
                "status": final_status,
                "message": f"Test {final_status}." if not err_msg else f"Test failed: {err_msg}",
                "requested_url": self._session.url,
                "current_url": latest_state.url if latest_state else self._session.url,
                "page_title": latest_state.title if latest_state else "",
                "duration_ms": latest_state.duration_ms if latest_state else None,
                "status_code": latest_state.status_code if latest_state else None,
                "screenshot_url": f"/api/tests/{self._session.id}/screenshot" if latest_state and latest_state.screenshot_path else None,
                "findings_count": len(all_findings),
                "ai_summary": ai_summary,
            })

            logger.info(
                "test_completed",
                component="orchestrator",
                test_id=self._session.id,
                status=final_status,
                findings=len(all_findings),
            )

        except DriverError as exc:
            logger.error(
                "driver_error",
                component="orchestrator",
                test_id=self._session.id,
                error=str(exc),
            )
            await self._repo.update_status(self._session.id, "failed", str(exc))
            await self._emit("status", {"status": "failed", "message": str(exc)})

        except Exception as exc:
            logger.error(
                "internal_error",
                component="orchestrator",
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
        if self._event_callback:
            try:
                await self._event_callback({"type": event_type, **data})
            except Exception as exc:
                logger.warning("event_emit_failed", component="orchestrator", error=str(exc))

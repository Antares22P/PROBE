"""
ReproductionEngine — Deterministic issue reproduction and confirmation engine for PROBE V1.

Flow:
Finding → Reset/recover state → Replay actions → Collect fresh evidence → Compare → Multi-attempt evaluation → Status determination
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.models import Action, ActionType, ApplicationState, PlatformType, TestConfig, TestSession
from app.detection.detector import Detector
from app.drivers.common.base import TestDriver
from app.evidence.models import format_action_signature, parse_action_signature
from app.findings.models import Finding, FindingStatus
from app.reproduction.models import AttemptRecord, ReproductionResult, ReproductionStatus
from app.storage.db_models import FindingModel, ReproductionModel
from app.storage.repository import TestRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ReproductionEngine:
    """
    Executes deterministic issue reproduction by replaying recorded structured actions
    and comparing fresh telemetry against the original finding signature.
    """

    def __init__(
        self,
        driver: TestDriver,
        session: TestSession,
        repository: Optional[TestRepository] = None,
    ) -> None:
        self._driver = driver
        self._session = session
        self._repo = repository

    async def reproduce(
        self,
        finding: Finding,
        attempts: int = 1,
        action_sequence: Optional[list[str]] = None,
    ) -> ReproductionResult:
        """
        Attempt to reproduce a finding across one or more attempts.
        """
        started_at = datetime.now(timezone.utc)
        logger.info(
            "reproduction_starting",
            component="ReproductionEngine",
            test_id=self._session.id,
            finding_id=finding.id,
            attempts=attempts,
        )

        # 1. Resolve structured action sequence
        resolved_sequence = self._extract_action_sequence(finding, action_sequence)
        logger.info(
            "reproduction_action_sequence",
            component="ReproductionEngine",
            test_id=self._session.id,
            finding_id=finding.id,
            steps_count=len(resolved_sequence),
            steps=resolved_sequence,
        )

        attempt_records: list[AttemptRecord] = []
        fresh_evidence_all: list[dict[str, Any]] = []
        successful_attempts = 0
        execution_errors = 0
        last_error: Optional[str] = None

        # 2. Multi-attempt replay loop
        for attempt_idx in range(1, attempts + 1):
            attempt_start = time.perf_counter()
            attempt_reproduced = False
            attempt_err: Optional[str] = None
            fresh_fps: list[str] = []

            try:
                # A. Reset / recover clean state
                await self._driver.reset_state()

                # B. Replay actions sequentially
                for step_sig in resolved_sequence:
                    action = parse_action_signature(step_sig)
                    if action.type == ActionType.NAVIGATE and action.value:
                        await self._driver.navigate(action.value)
                    else:
                        res = await self._driver.execute_action(action)
                        if res.error:
                            logger.warning(
                                "reproduction_action_failed",
                                component="ReproductionEngine",
                                step=step_sig,
                                error=res.error,
                            )

                    # Small settle delay between actions
                    await asyncio.sleep(0.1)

                # C. Capture fresh state and evaluate
                fresh_state = await self._driver.get_current_state()

                # D. Run fresh issue detection
                fresh_detector = Detector(test_id=self._session.id)
                fresh_findings = fresh_detector.detect(fresh_state)
                fresh_fps = [f.fingerprint for f in fresh_findings if f.fingerprint]

                # E. Compare fresh findings with original finding
                attempt_reproduced = self._is_reproduced(finding, fresh_findings, fresh_state)

                if attempt_reproduced:
                    successful_attempts += 1
                    # Extract fresh evidence items
                    for ff in fresh_findings:
                        if ff.fingerprint == finding.fingerprint or ff.category == finding.category:
                            for ev in ff.evidence:
                                fresh_evidence_all.append(ev)

                    if not fresh_findings and fresh_state.error:
                        fresh_evidence_all.append({
                            "type": "navigation_failure",
                            "error": fresh_state.error,
                            "url": fresh_state.url,
                            "timestamp": str(datetime.now(timezone.utc)),
                        })

            except Exception as exc:
                execution_errors += 1
                attempt_err = str(exc)
                last_error = str(exc)
                logger.warning(
                    "reproduction_attempt_exception",
                    component="ReproductionEngine",
                    attempt=attempt_idx,
                    error=str(exc),
                )

            attempt_dur = round((time.perf_counter() - attempt_start) * 1000, 2)
            attempt_records.append(
                AttemptRecord(
                    attempt_number=attempt_idx,
                    reproduced=attempt_reproduced,
                    duration_ms=attempt_dur,
                    error=attempt_err,
                    fresh_signals_count=len(fresh_fps),
                    fresh_fingerprints=fresh_fps,
                )
            )

        # 3. Determine Overall Reproduction Status
        if execution_errors == attempts:
            status = ReproductionStatus.FAILED
        elif successful_attempts == attempts and attempts > 0:
            status = ReproductionStatus.REPRODUCED
        elif successful_attempts == 0:
            status = ReproductionStatus.NOT_REPRODUCED
        else:
            status = ReproductionStatus.INTERMITTENT

        # 4. Confirmation Lifecycle Update
        if status == ReproductionStatus.REPRODUCED:
            finding.status = FindingStatus.CONFIRMED
        elif status == ReproductionStatus.NOT_REPRODUCED:
            finding.status = FindingStatus.UNCONFIRMED
        elif status == ReproductionStatus.INTERMITTENT:
            finding.status = FindingStatus.INVESTIGATING

        completed_at = datetime.now(timezone.utc)
        result = ReproductionResult(
            test_id=self._session.id,
            finding_id=finding.id,
            status=status,
            attempts=attempts,
            successful_attempts=successful_attempts,
            action_sequence=resolved_sequence,
            fresh_evidence=fresh_evidence_all,
            attempt_records=attempt_records,
            error_message=last_error if status == ReproductionStatus.FAILED else None,
            started_at=started_at,
            completed_at=completed_at,
        )

        logger.info(
            "reproduction_completed",
            component="ReproductionEngine",
            test_id=self._session.id,
            finding_id=finding.id,
            status=status.value,
            successful_attempts=successful_attempts,
            total_attempts=attempts,
            confirmed=(finding.status == FindingStatus.CONFIRMED),
        )

        # 5. Persist to Repository if available
        if self._repo:
            try:
                rep_model = ReproductionModel(
                    id=result.id,
                    test_id=self._session.id,
                    finding_id=finding.id,
                    status=result.status.value,
                    attempts=result.attempts,
                    successful_attempts=result.successful_attempts,
                    steps=result.action_sequence,
                    fresh_evidence=result.fresh_evidence,
                    error_message=result.error_message,
                    created_at=result.started_at,
                    completed_at=result.completed_at,
                )
                await self._repo.add_reproduction(rep_model)

                # Update finding status in database
                db_finding = await self._repo.get_finding_by_fingerprint(
                    self._session.id, finding.fingerprint or ""
                )
                if not db_finding:
                    findings = await self._repo.get_findings(self._session.id)
                    db_finding = next((f for f in findings if f.id == finding.id), None)

                if db_finding:
                    db_finding.status = finding.status.value
                    await self._repo.update_finding(db_finding)

            except Exception as exc:
                logger.warning(
                    "reproduction_persist_error",
                    component="ReproductionEngine",
                    error=str(exc),
                )

        return result

    def _extract_action_sequence(
        self,
        finding: Finding,
        explicit_sequence: Optional[list[str]],
    ) -> list[str]:
        """Resolve the replayable action sequence for the finding."""
        if explicit_sequence:
            return explicit_sequence

        if finding.reproduction and isinstance(finding.reproduction, dict):
            # Check for explicit action sequence in reproduction dict
            if "action_sequence" in finding.reproduction:
                seq = finding.reproduction["action_sequence"]
                if isinstance(seq, list) and len(seq) > 0:
                    return [str(s) for s in seq]

            if "steps" in finding.reproduction:
                steps = finding.reproduction["steps"]
                if isinstance(steps, list) and len(steps) > 0:
                    return [
                        s if isinstance(s, str) else format_action_signature(Action(**s))
                        for s in steps
                    ]

            # If reproduction recorded a single action (e.g. click/type)
            if "action_type" in finding.reproduction:
                try:
                    act = Action(
                        type=ActionType(finding.reproduction.get("action_type", "click")),
                        target=finding.reproduction.get("target"),
                        value=finding.reproduction.get("value"),
                    )
                    # Prepend navigation to target URL if available
                    nav_url = finding.reproduction.get("url") or self._session.url
                    return [f'NAVIGATE("{nav_url}")', format_action_signature(act)]
                except Exception:
                    pass

        # Fallback: Navigate to the affected URL or session URL
        target_url = self._session.url
        for ev in finding.evidence:
            if isinstance(ev, dict) and ev.get("url"):
                target_url = ev["url"]
                break
            elif isinstance(ev, dict) and ev.get("page_url"):
                target_url = ev["page_url"]
                break

        return [f'NAVIGATE("{target_url}")']

    def _is_reproduced(
        self,
        finding: Finding,
        fresh_findings: list[Finding],
        fresh_state: ApplicationState,
    ) -> bool:
        """
        Compare fresh state & findings against original finding signature.
        """
        # 1. Exact fingerprint match
        if finding.fingerprint:
            for ff in fresh_findings:
                if ff.fingerprint == finding.fingerprint:
                    return True

        # 2. Match by category and core error text
        for ff in fresh_findings:
            if ff.category == finding.category:
                # Check description / title similarity
                if finding.title.lower() in ff.title.lower() or ff.title.lower() in finding.title.lower():
                    return True

        # 3. Direct state signal checks
        if finding.category == "javascript":
            # Check if any JS exception matches
            for ex in fresh_state.js_exceptions:
                if ex.message and ex.message in finding.description:
                    return True
            for cmsg in fresh_state.console_messages:
                if cmsg.level == "error" and cmsg.text and cmsg.text in finding.description:
                    return True

        elif finding.category == "network":
            for req in fresh_state.failed_requests:
                if req.url and req.url in finding.description:
                    return True
            for ev in fresh_state.network_events:
                if ev.status and str(ev.status) in finding.title:
                    return True
            if fresh_state.status_code and str(fresh_state.status_code) in finding.title:
                return True

        elif finding.category == "ui" and "Blank Page" in finding.title:
            if len(fresh_state.elements) == 0 and not fresh_state.visible_text.strip():
                return True

        elif finding.category == "functional" and fresh_state.error:
            if fresh_state.error in finding.description or "Navigation Failure" in finding.title:
                return True

        return False

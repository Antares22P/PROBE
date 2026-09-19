"""
Detector — heuristic problem detection.

Analyzes ApplicationState for common issues:
- Console errors
- Broken network requests (4xx, 5xx)
- Missing page title
- Empty page content
"""
from __future__ import annotations

from app.core.models import ApplicationState
from app.findings.models import Finding, FindingSeverity
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Detector:
    """Detects problems in an ApplicationState."""

    def __init__(self, test_id: str) -> None:
        self._test_id = test_id

    def detect(self, state: ApplicationState) -> list[Finding]:
        """Run all detectors against the given state."""
        findings: list[Finding] = []
        findings.extend(self._detect_console_errors(state))
        findings.extend(self._detect_network_errors(state))
        findings.extend(self._detect_empty_page(state))
        return findings

    def _detect_console_errors(self, state: ApplicationState) -> list[Finding]:
        findings = []
        for error in state.console_errors:
            findings.append(
                Finding(
                    test_id=self._test_id,
                    severity=FindingSeverity.MEDIUM,
                    category="console_error",
                    title="Console Error Detected",
                    description=error[:500],
                )
            )
        return findings

    def _detect_network_errors(self, state: ApplicationState) -> list[Finding]:
        findings = []
        for evt in state.network_events:
            if evt.status is not None and evt.status >= 400:
                severity = FindingSeverity.HIGH if evt.status >= 500 else FindingSeverity.MEDIUM
                findings.append(
                    Finding(
                        test_id=self._test_id,
                        severity=severity,
                        category="network_error",
                        title=f"HTTP {evt.status} Error",
                        description=f"{evt.method} {evt.url} returned {evt.status}",
                    )
                )
        return findings

    def _detect_empty_page(self, state: ApplicationState) -> list[Finding]:
        findings = []
        if not state.title or state.title.strip() == "":
            findings.append(
                Finding(
                    test_id=self._test_id,
                    severity=FindingSeverity.LOW,
                    category="missing_title",
                    title="Page Has No Title",
                    description=f"The page at {state.url} has no <title>.",
                )
            )
        return findings

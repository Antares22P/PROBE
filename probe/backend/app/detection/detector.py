"""
Detector — Deterministic, rule-based issue detection engine for PROBE V1.

Detects:
- Network: HTTP 4xx, HTTP 5xx, failed network requests, high latency timeouts
- JavaScript: uncaught exceptions (pageerror), console errors
- Navigation: navigation failures, unexpected blank pages
- Links: broken links (404/5xx on navigation)
- Browser: crash / automation timeouts

Features:
- Structured Finding generation with categories, severities, statuses, confidence, and evidence.
- Stable finding fingerprinting for robust deduplication.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Optional

from app.core.models import ApplicationState
from app.findings.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    compute_finding_fingerprint,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Detector:
    """
    Deterministic issue detection engine for PROBE V1.

    Maintains session finding deduplication by fingerprint.
    """

    def __init__(self, test_id: str) -> None:
        self._test_id = test_id
        self._findings: dict[str, Finding] = {}  # fingerprint -> Finding

    def detect(
        self,
        state: ApplicationState,
        action_context: Optional[dict[str, Any]] = None,
    ) -> list[Finding]:
        """
        Run all deterministic detectors against an ApplicationState.

        Returns newly discovered or updated findings.
        """
        new_findings: list[Finding] = []

        # 1. Navigation & Page Errors
        self._detect_navigation_failure(state, new_findings, action_context)
        self._detect_blank_page(state, new_findings)

        # 2. JavaScript Issues (Uncaught Exceptions & Console Errors)
        self._detect_js_exceptions(state, new_findings, action_context)
        self._detect_console_errors(state, new_findings, action_context)

        # 3. Network Issues (Failed Requests, HTTP 4xx, HTTP 5xx)
        self._detect_failed_requests(state, new_findings, action_context)
        self._detect_http_status_errors(state, new_findings, action_context)

        return new_findings

    @property
    def all_findings(self) -> list[Finding]:
        """Return all deduplicated findings discovered so far."""
        return list(self._findings.values())

    # ------------------------------------------------------------------
    # 1. Navigation Detectors
    # ------------------------------------------------------------------

    def _detect_navigation_failure(
        self,
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
    ) -> None:
        if not state.error:
            return

        target_url = state.requested_url or state.url or "unknown"
        error_text = state.error.strip()
        fp = compute_finding_fingerprint("functional", "navigation_error", target_url, error_text)

        severity = FindingSeverity.CRITICAL if not state.url else FindingSeverity.HIGH

        evidence_item = {
            "type": "navigation_failure",
            "requested_url": state.requested_url,
            "final_url": state.url,
            "error": error_text,
            "duration_ms": state.duration_ms,
            "screenshot_path": state.screenshot_path,
        }

        finding = self._get_or_create_finding(
            fingerprint=fp,
            title=f"Navigation Failure: {self._short_text(error_text, 60)}",
            category=FindingCategory.FUNCTIONAL,
            severity=severity,
            status=FindingStatus.POTENTIAL,
            confidence=0.95,
            description=f"Navigation to '{target_url}' failed: {error_text}",
            evidence_item=evidence_item,
            reproduction=action_context,
            recommendation="Verify URL syntax, DNS resolution, host reachability, and network firewall policies.",
        )
        if finding:
            results.append(finding)

    def _detect_blank_page(
        self, state: ApplicationState, results: list[Finding]
    ) -> None:
        # Check if HTTP was 200 OK but page is blank
        if (
            state.url
            and not state.url.startswith("about:blank")
            and not state.error
            and state.status_code == 200
            and len(state.elements) == 0
            and (not state.visible_text or not state.visible_text.strip())
        ):
            fp = compute_finding_fingerprint("ui", "blank_page", state.url, "empty_body_200")
            evidence_item = {
                "type": "blank_page",
                "url": state.url,
                "status_code": 200,
                "element_count": 0,
                "screenshot_path": state.screenshot_path,
            }

            finding = self._get_or_create_finding(
                fingerprint=fp,
                title="Unexpected Blank Page Rendered (HTTP 200)",
                category=FindingCategory.UI,
                severity=FindingSeverity.HIGH,
                status=FindingStatus.POTENTIAL,
                confidence=0.85,
                description=f"The application returned HTTP 200 OK at '{state.url}', but rendered an entirely blank page with zero visible text or interactive elements.",
                evidence_item=evidence_item,
                recommendation="Check for unmounted frontend roots, missing bundle scripts, client-side crashes before paint, or CSS 'display: none' rules on body.",
            )
            if finding:
                results.append(finding)

    # ------------------------------------------------------------------
    # 2. JavaScript Detectors
    # ------------------------------------------------------------------

    def _detect_js_exceptions(
        self,
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
    ) -> None:
        for ex in state.js_exceptions:
            msg = ex.message.strip()
            if not msg:
                continue

            fp = compute_finding_fingerprint("javascript", "uncaught_exception", state.url, msg)
            evidence_item = {
                "type": "javascript_exception",
                "message": msg,
                "stack": ex.stack,
                "url": state.url,
                "timestamp": str(ex.timestamp),
                "screenshot_path": state.screenshot_path,
            }

            finding = self._get_or_create_finding(
                fingerprint=fp,
                title=f"JavaScript Exception: {self._short_text(msg, 70)}",
                category=FindingCategory.JAVASCRIPT,
                severity=FindingSeverity.HIGH,
                status=FindingStatus.POTENTIAL,
                confidence=0.95,
                description=f"An uncaught JavaScript runtime error was thrown on '{state.url}':\n{msg}",
                evidence_item=evidence_item,
                reproduction=action_context,
                recommendation="Inspect client-side script code and stack trace to fix unhandled null pointers, type errors, or missing imports.",
            )
            if finding:
                results.append(finding)

    def _detect_console_errors(
        self,
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
    ) -> None:
        # Check structured console messages
        for cmsg in state.console_messages:
            if cmsg.level in ("error",):
                text = cmsg.text.strip()
                if not text:
                    continue

                fp = compute_finding_fingerprint("javascript", "console_error", state.url, text)
                evidence_item = {
                    "type": "console_error",
                    "level": cmsg.level,
                    "text": text,
                    "location": cmsg.location,
                    "url": state.url,
                    "timestamp": str(cmsg.timestamp),
                }

                finding = self._get_or_create_finding(
                    fingerprint=fp,
                    title=f"Browser Console Error: {self._short_text(text, 80)}",
                    category=FindingCategory.JAVASCRIPT,
                    severity=FindingSeverity.MEDIUM,
                    status=FindingStatus.POTENTIAL,
                    confidence=0.85,
                    description=f"Browser console recorded an error on '{state.url}':\n{text}",
                    evidence_item=evidence_item,
                    reproduction=action_context,
                    recommendation="Review client-side console error logs and resource references.",
                )
                if finding:
                    results.append(finding)

    # ------------------------------------------------------------------
    # 3. Network Detectors
    # ------------------------------------------------------------------

    def _detect_failed_requests(
        self,
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
    ) -> None:
        for req in state.failed_requests:
            url_clean = req.url.strip()
            fail_text = req.failure_text.strip() or "Request Failed"

            fp = compute_finding_fingerprint("network", "failed_request", url_clean, fail_text)
            parsed = urllib.parse.urlparse(url_clean)
            short_path = parsed.path or url_clean

            evidence_item = {
                "type": "failed_network_request",
                "url": url_clean,
                "method": req.method,
                "failure_text": fail_text,
                "status": req.status,
                "page_url": state.url,
                "timestamp": str(req.timestamp),
            }

            finding = self._get_or_create_finding(
                fingerprint=fp,
                title=f"Failed Network Request ({req.method} {self._short_text(short_path, 40)})",
                category=FindingCategory.NETWORK,
                severity=FindingSeverity.HIGH,
                status=FindingStatus.POTENTIAL,
                confidence=0.90,
                description=f"Network request '{req.method} {url_clean}' failed with error: {fail_text}",
                evidence_item=evidence_item,
                reproduction=action_context,
                recommendation="Check target endpoint availability, CORS policies, SSL certificates, and network stability.",
            )
            if finding:
                results.append(finding)

    def _detect_http_status_errors(
        self,
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
    ) -> None:
        # Check main page navigation status
        if state.status_code is not None and state.status_code >= 400:
            self._process_http_status(
                url=state.url or state.requested_url,
                method="GET",
                status_code=state.status_code,
                duration_ms=state.duration_ms,
                state=state,
                results=results,
                action_context=action_context,
                is_main_navigation=True,
            )

        # Check background network events
        for evt in state.network_events:
            if evt.status is not None and evt.status >= 400:
                self._process_http_status(
                    url=evt.url,
                    method=evt.method,
                    status_code=evt.status,
                    duration_ms=evt.duration_ms,
                    state=state,
                    results=results,
                    action_context=action_context,
                    is_main_navigation=False,
                )

    def _process_http_status(
        self,
        url: str,
        method: str,
        status_code: int,
        duration_ms: Optional[float],
        state: ApplicationState,
        results: list[Finding],
        action_context: Optional[dict[str, Any]],
        is_main_navigation: bool,
    ) -> None:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path or url
        fp = compute_finding_fingerprint("network", f"http_{status_code}", url, f"status_{status_code}")

        is_5xx = status_code >= 500
        severity = (
            FindingSeverity.CRITICAL if (is_5xx and is_main_navigation)
            else FindingSeverity.HIGH if is_5xx
            else FindingSeverity.MEDIUM
        )

        title_prefix = "HTTP 5xx Server Error" if is_5xx else "HTTP 4xx Client Error"
        if status_code == 404:
            title = f"HTTP 404 Not Found: {self._short_text(path, 40)}"
            recommendation = "Verify the route path exists and static assets are correctly deployed."
        elif status_code in (401, 403):
            title = f"HTTP {status_code} Access Denied: {self._short_text(path, 40)}"
            recommendation = "Check authentication tokens, session cookies, and route permission rules."
        elif status_code == 500:
            title = f"HTTP 500 Internal Server Error on {self._short_text(path, 40)}"
            recommendation = "Inspect backend server logs for unhandled exceptions or database connection failures."
        else:
            title = f"{title_prefix} (HTTP {status_code}) on {self._short_text(path, 40)}"
            recommendation = "Check server endpoint status codes and API gateway configurations."

        evidence_item = {
            "type": "http_status_error",
            "url": url,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "is_main_navigation": is_main_navigation,
            "page_url": state.url,
            "screenshot_path": state.screenshot_path if is_main_navigation else None,
        }

        finding = self._get_or_create_finding(
            fingerprint=fp,
            title=title,
            category=FindingCategory.NETWORK,
            severity=severity,
            status=FindingStatus.POTENTIAL,
            confidence=0.90 if is_5xx else 0.85,
            description=f"HTTP request '{method} {url}' returned status code {status_code}.",
            evidence_item=evidence_item,
            reproduction=action_context,
            recommendation=recommendation,
        )
        if finding:
            results.append(finding)

    # ------------------------------------------------------------------
    # Deduplication Helper
    # ------------------------------------------------------------------

    def _get_or_create_finding(
        self,
        fingerprint: str,
        title: str,
        category: FindingCategory,
        severity: FindingSeverity,
        status: FindingStatus,
        confidence: float,
        description: str,
        evidence_item: dict[str, Any],
        reproduction: Optional[dict[str, Any]] = None,
        recommendation: Optional[str] = None,
    ) -> Optional[Finding]:
        """
        Deduplicate finding by fingerprint.

        If already discovered in this session:
        - Appends new evidence occurrence.
        - Does NOT create a duplicate finding.
        If new:
        - Creates, registers, and returns the new Finding.
        """
        if fingerprint in self._findings:
            existing = self._findings[fingerprint]
            # Append evidence if not already recorded
            if evidence_item not in existing.evidence:
                existing.evidence.append(evidence_item)
            return None

        finding = Finding(
            test_id=self._test_id,
            title=title,
            category=category,
            severity=severity,
            status=status,
            confidence=confidence,
            description=description,
            evidence=[evidence_item],
            reproduction=reproduction,
            recommendation=recommendation,
            fingerprint=fingerprint,
        )
        self._findings[fingerprint] = finding
        logger.info(
            "finding_detected",
            component="Detector",
            test_id=self._test_id,
            category=category.value,
            severity=severity.value,
            title=title,
            fingerprint=fingerprint,
        )
        return finding

    def _short_text(self, text: str, max_len: int = 50) -> str:
        t = text.replace("\n", " ").strip()
        return t if len(t) <= max_len else f"{t[:max_len]}..."

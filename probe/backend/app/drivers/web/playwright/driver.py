"""
WebTestDriver — Playwright implementation of TestDriver.

This is the ONLY file in PROBE that imports Playwright.
PROBE Core must never import from this module directly;
it always works through the TestDriver ABC.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    Request,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from app.core.models import (
    Action,
    ActionType,
    ApplicationState,
    Bounds,
    ConsoleMessage,
    Dimensions,
    Element,
    Evidence,
    EvidenceType,
    FailedRequest,
    JavaScriptException,
    NetworkEvent,
    TestConfig,
    TestSession,
    Viewport,
    compute_state_fingerprint,
)
from app.drivers.common.base import TestDriver
from app.storage.artifacts import default_artifact_storage
from app.utils.errors import DriverError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WebTestDriver(TestDriver):
    """
    Playwright-based web test driver.

    Implements the platform-neutral TestDriver interface using
    Playwright for Python. PROBE Core never imports this class directly.
    """

    def __init__(self, session: TestSession, config: TestConfig) -> None:
        super().__init__(session, config)
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._network_events: list[NetworkEvent] = []
        self._console_messages: list[ConsoleMessage] = []
        self._console_errors: list[str] = []
        self._js_exceptions: list[JavaScriptException] = []
        self._failed_requests: list[FailedRequest] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Launch Playwright + Chromium and set up an isolated browser context."""
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._config.headless,
            )
            # Create isolated context for this test session
            self._context = await self._browser.new_context(
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                }
            )
            self._page = await self._context.new_page()

            # Signal & telemetry listeners
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            self._page.on("requestfailed", self._on_request_failed)
            self._page.on("pageerror", self._on_page_error)
            self._page.on("console", self._on_console)

            self._initialized = True
            logger.info(
                "playwright_ready",
                component="WebTestDriver",
                test_id=self._session.id,
            )
        except Exception as exc:
            raise DriverError(f"Failed to initialize WebTestDriver: {exc}") from exc

    async def close(self) -> None:
        """Tear down Playwright resources."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.warning("driver_close_error", component="WebTestDriver", error=str(exc))
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            self._initialized = False

    async def reset_state(self) -> None:
        """Clear cookies, storage, and navigate to blank."""
        if not self._context:
            raise DriverError("Driver not initialized")
        await self._context.clear_cookies()
        if self._page and not self._page.is_closed():
            await self._page.goto("about:blank")
        self._network_events.clear()
        self._console_messages.clear()
        self._console_errors.clear()
        self._js_exceptions.clear()
        self._failed_requests.clear()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> ApplicationState:
        """
        Navigate to a URL with complete telemetry recording.
        """
        page = self._require_page()
        start_time = time.perf_counter()
        status_code: Optional[int] = None
        nav_error: Optional[str] = None

        url_clean = url.strip()
        if not url_clean:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return ApplicationState(
                requested_url=url,
                url="",
                title="",
                status_code=None,
                duration_ms=duration_ms,
                error="URL cannot be empty",
            )

        try:
            # Check for supported schemes
            valid_prefixes = ("http://", "https://", "data:", "file://", "about:")
            if not any(url_clean.startswith(p) for p in valid_prefixes):
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return ApplicationState(
                    requested_url=url,
                    url=page.url if not page.is_closed() else "",
                    title="",
                    status_code=None,
                    duration_ms=duration_ms,
                    error=f"Invalid URL protocol: '{url}'. Must start with http:// or https://",
                )

            # Navigation timeout
            timeout_ms = (
                min(self._config.timeout_seconds * 1000, 60000)
                if hasattr(self._config, "timeout_seconds") and self._config.timeout_seconds > 0
                else 30000
            )

            response = await page.goto(
                url_clean,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if response:
                status_code = response.status

            state = await self.get_current_state()
            state.requested_url = url
            state.status_code = status_code
            state.duration_ms = duration_ms
            return state

        except PlaywrightTimeoutError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            nav_error = f"Navigation timed out after {duration_ms}ms"
            logger.warning(
                "navigation_timeout",
                component="WebTestDriver",
                test_id=self._session.id,
                url=url,
                duration_ms=duration_ms,
            )
            current_url = page.url if not page.is_closed() else url
            title = ""
            try:
                if not page.is_closed():
                    title = await page.title()
            except Exception:
                pass

            return ApplicationState(
                requested_url=url,
                url=current_url,
                title=title,
                status_code=status_code,
                duration_ms=duration_ms,
                error=nav_error,
                network_events=list(self._network_events),
                console_messages=list(self._console_messages),
                console_errors=list(self._console_errors),
                js_exceptions=list(self._js_exceptions),
                failed_requests=list(self._failed_requests),
            )

        except PlaywrightError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            err_msg = str(exc)
            if "ERR_NAME_NOT_RESOLVED" in err_msg:
                nav_error = f"DNS resolution failed: {url}"
            elif "ERR_CONNECTION_REFUSED" in err_msg:
                nav_error = f"Connection refused: {url}"
            elif "ERR_CONNECTION_TIMED_OUT" in err_msg:
                nav_error = f"Connection timed out: {url}"
            elif "Cannot navigate to invalid URL" in err_msg or "Invalid URL" in err_msg:
                nav_error = f"Invalid URL: {url}"
            else:
                first_line = err_msg.splitlines()[0] if err_msg else "Unknown navigation error"
                nav_error = f"Navigation failed: {first_line}"

            logger.warning(
                "navigation_error",
                component="WebTestDriver",
                test_id=self._session.id,
                url=url,
                error=nav_error,
            )
            current_url = page.url if not page.is_closed() else url
            return ApplicationState(
                requested_url=url,
                url=current_url,
                title="",
                status_code=status_code,
                duration_ms=duration_ms,
                error=nav_error,
                network_events=list(self._network_events),
                console_messages=list(self._console_messages),
                console_errors=list(self._console_errors),
                js_exceptions=list(self._js_exceptions),
                failed_requests=list(self._failed_requests),
            )

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            nav_error = f"Navigation failed: {str(exc)}"
            logger.error(
                "navigation_unexpected_error",
                component="WebTestDriver",
                test_id=self._session.id,
                url=url,
                error=str(exc),
            )
            return ApplicationState(
                requested_url=url,
                url=page.url if not page.is_closed() else url,
                title="",
                status_code=None,
                duration_ms=duration_ms,
                error=nav_error,
            )

    # ------------------------------------------------------------------
    # Deep Observation Pipeline
    # ------------------------------------------------------------------

    async def get_current_state(self) -> ApplicationState:
        """
        Deep observation snapshot:
        - URL, Title
        - Viewport & Page dimensions
        - Visible text
        - All interactive elements with complete metadata
        - Signals (console, errors, exceptions, failed network requests)
        - Deterministic state fingerprint
        """
        page = self._require_page()
        try:
            url = page.url
            title = await page.title()

            # Execute evaluation script to extract elements, viewport, dimensions, and text in one pass
            dom_data = await page.evaluate("""
                () => {
                    const vpWidth = window.innerWidth || (document.documentElement ? document.documentElement.clientWidth : 0) || 1280;
                    const vpHeight = window.innerHeight || (document.documentElement ? document.documentElement.clientHeight : 0) || 720;
                    const scrollW = Math.max(
                        document.body ? document.body.scrollWidth : 0,
                        document.documentElement ? document.documentElement.scrollWidth : 0,
                        vpWidth
                    );
                    const scrollH = Math.max(
                        document.body ? document.body.scrollHeight : 0,
                        document.documentElement ? document.documentElement.scrollHeight : 0,
                        vpHeight
                    );

                    const visibleText = document.body ? (document.body.innerText || '').trim() : '';

                    function getElementLabel(el) {
                        if (el.getAttribute('aria-label')) {
                            return el.getAttribute('aria-label').trim();
                        }
                        if (el.getAttribute('aria-labelledby')) {
                            const labelEl = document.getElementById(el.getAttribute('aria-labelledby'));
                            if (labelEl && labelEl.textContent) return labelEl.textContent.trim();
                        }
                        if (el.labels && el.labels.length > 0) {
                            const lblTexts = Array.from(el.labels).map(l => l.textContent.trim()).filter(Boolean);
                            if (lblTexts.length > 0) return lblTexts.join(' ');
                        }
                        if (el.id) {
                            try {
                                const labelFor = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                                if (labelFor && labelFor.textContent) return labelFor.textContent.trim();
                            } catch (e) {}
                        }
                        if (el.placeholder) return el.placeholder.trim();
                        if (el.title) return el.title.trim();
                        if (el.getAttribute('alt')) return el.getAttribute('alt').trim();
                        if (el.name) return el.name.trim();
                        return '';
                    }

                    function getCssSelector(el) {
                        if (el.id) {
                            try {
                                return `#${CSS.escape(el.id)}`;
                            } catch (e) {
                                return `#${el.id}`;
                            }
                        }
                        if (el.name && ['input', 'select', 'textarea'].includes(el.tagName.toLowerCase())) {
                            try {
                                return `${el.tagName.toLowerCase()}[name="${CSS.escape(el.name)}"]`;
                            } catch (e) {}
                        }
                        if (el.getAttribute('data-testid')) {
                            return `[data-testid="${el.getAttribute('data-testid')}"]`;
                        }
                        let path = [];
                        let curr = el;
                        while (curr && curr.nodeType === Node.ELEMENT_NODE && curr !== document.documentElement && path.length < 5) {
                            let selector = curr.tagName.toLowerCase();
                            if (curr.id) {
                                path.unshift(`#${curr.id}`);
                                break;
                            }
                            let sibling = curr;
                            let nth = 1;
                            while (sibling = sibling.previousElementSibling) {
                                if (sibling.tagName.toLowerCase() === selector) nth++;
                            }
                            if (nth > 1) {
                                selector += `:nth-of-type(${nth})`;
                            }
                            path.unshift(selector);
                            curr = curr.parentElement;
                        }
                        return path.join(' > ');
                    }

                    const selectors = [
                        'a[href]', 'button', 'input', 'textarea', 'select', 'form',
                        '[role="button"]', '[role="link"]', '[role="checkbox"]',
                        '[role="radio"]', '[role="tab"]', '[role="menuitem"]',
                        '[role="switch"]', '[tabindex]:not([tabindex="-1"])', '[onclick]'
                    ];

                    const candidates = Array.from(document.querySelectorAll(selectors.join(', ')));
                    const elements = [];
                    const seen = new Set();

                    for (const el of candidates) {
                        if (seen.has(el)) continue;
                        seen.add(el);

                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        const isHidden = style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
                        const visible = !isHidden && (rect.width > 0 || rect.height > 0 || el.tagName.toLowerCase() === 'form');

                        const tag = el.tagName.toLowerCase();
                        let elType = tag;
                        if (tag === 'input') {
                            const inputType = (el.type || 'text').toLowerCase();
                            elType = inputType === 'checkbox' ? 'checkbox' : inputType === 'radio' ? 'radio' : `input:${inputType}`;
                        } else if (tag === 'a') {
                            elType = 'link';
                        } else if (tag === 'button' || el.getAttribute('role') === 'button') {
                            elType = 'button';
                        } else if (tag === 'textarea') {
                            elType = 'textarea';
                        } else if (tag === 'select') {
                            elType = 'select';
                        } else if (tag === 'form') {
                            elType = 'form';
                        }

                        const role = el.getAttribute('role') || (tag === 'a' ? 'link' : tag === 'button' ? 'button' : tag === 'form' ? 'form' : tag);
                        let text = '';
                        if (tag === 'input' && ['button', 'submit', 'reset'].includes((el.type || '').toLowerCase())) {
                            text = (el.value || '').trim();
                        } else {
                            text = (el.textContent || '').trim().slice(0, 300);
                        }

                        const label = getElementLabel(el);
                        const reference = getCssSelector(el);
                        const enabled = !el.disabled && el.getAttribute('aria-disabled') !== 'true';

                        const attrs = {};
                        for (const attr of el.attributes) {
                            attrs[attr.name] = attr.value;
                        }

                        elements.push({
                            id: el.id || '',
                            tag: tag,
                            type: elType,
                            role: role,
                            text: text,
                            label: label,
                            reference: reference,
                            selector: reference,
                            visible: visible,
                            enabled: enabled,
                            bounding_box: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                            },
                            bounds: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                            },
                            is_interactive: true,
                            attributes: attrs,
                        });
                    }

                    return {
                        viewport: { width: Math.round(vpWidth), height: Math.round(vpHeight) },
                        page_dimensions: { width: Math.round(scrollW), height: Math.round(scrollH) },
                        visible_text: visibleText.slice(0, 10000),
                        elements: elements.slice(0, 300),
                    };
                }
            """)

            viewport = Viewport(
                width=dom_data["viewport"]["width"],
                height=dom_data["viewport"]["height"],
            )
            dimensions = Dimensions(
                width=float(dom_data["page_dimensions"]["width"]),
                height=float(dom_data["page_dimensions"]["height"]),
            )
            visible_text = dom_data.get("visible_text", "")

            parsed_elements: list[Element] = []
            for item in dom_data.get("elements", []):
                bbox = Bounds(**item["bounding_box"]) if item.get("bounding_box") else None
                elem = Element(
                    id=item.get("id") or str(uuid.uuid4()),
                    tag=item.get("tag", ""),
                    type=item.get("type", ""),
                    role=item.get("role", ""),
                    text=item.get("text", ""),
                    label=item.get("label", ""),
                    reference=item.get("reference", ""),
                    selector=item.get("selector", ""),
                    visible=item.get("visible", True),
                    enabled=item.get("enabled", True),
                    bounding_box=bbox,
                    bounds=bbox,
                    is_interactive=True,
                    attributes=item.get("attributes", {}),
                )
                parsed_elements.append(elem)

            # Compute state fingerprint
            fingerprint = compute_state_fingerprint(
                url=url,
                title=title,
                elements=parsed_elements,
                visible_text=visible_text,
            )

            return ApplicationState(
                url=url,
                title=title,
                visible_text=visible_text,
                viewport=viewport,
                page_dimensions=dimensions,
                elements=parsed_elements,
                console_messages=list(self._console_messages),
                console_errors=list(self._console_errors),
                js_exceptions=list(self._js_exceptions),
                failed_requests=list(self._failed_requests),
                network_events=list(self._network_events),
                fingerprint=fingerprint,
            )
        except Exception as exc:
            raise DriverError(f"Failed to capture state: {exc}") from exc

    async def get_interactive_elements(self) -> list[Element]:
        state = await self.get_current_state()
        return state.elements

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def execute_action(self, action: Action) -> ApplicationState:
        page = self._require_page()
        try:
            if action.type == ActionType.NAVIGATE:
                return await self.navigate(action.value or "")

            elif action.type == ActionType.CLICK:
                if action.target:
                    await page.click(action.target, timeout=5000)

            elif action.type == ActionType.TYPE:
                if action.target and action.value is not None:
                    await page.fill(action.target, action.value)

            elif action.type == ActionType.SELECT:
                if action.target and action.value is not None:
                    await page.select_option(action.target, action.value)

            elif action.type == ActionType.SCROLL:
                delta_y = int(action.value or "300")
                await page.mouse.wheel(0, delta_y)

            elif action.type == ActionType.WAIT:
                ms = int(action.value or "1000")
                await asyncio.sleep(ms / 1000)

            elif action.type == ActionType.SCREENSHOT:
                await self.capture_screenshot()

            elif action.type == ActionType.BACK:
                await page.go_back(timeout=5000)

            elif action.type in (ActionType.SWIPE,):
                raise DriverError(f"Action {action.type} not supported on web platform")

            else:
                raise DriverError(f"Unknown action type: {action.type}")

            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            return await self.get_current_state()

        except DriverError:
            raise
        except Exception as exc:
            raise DriverError(f"Action {action.type} failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Evidence Collection
    # ------------------------------------------------------------------

    async def capture_screenshot(self, path: Optional[str] = None) -> Evidence:
        page = self._require_page()
        try:
            image_bytes = await page.screenshot(full_page=False)
            if path is None:
                saved_path = await default_artifact_storage.save_screenshot(
                    test_id=self._session.id,
                    image_bytes=image_bytes,
                )
            else:
                with open(path, "wb") as f:
                    f.write(image_bytes)
                saved_path = path

            logger.info(
                "screenshot_captured",
                component="WebTestDriver",
                test_id=self._session.id,
                path=saved_path,
            )
            return Evidence(
                type=EvidenceType.SCREENSHOT,
                screenshot_path=saved_path,
            )
        except Exception as exc:
            raise DriverError(f"Screenshot failed: {exc}") from exc

    async def collect_logs(self) -> list[str]:
        return list(self._console_errors)

    async def collect_network_events(self) -> list[NetworkEvent]:
        return list(self._network_events)

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------

    def _on_request(self, request: Request) -> None:
        self._network_events.append(
            NetworkEvent(
                url=request.url,
                method=request.method,
            )
        )

    def _on_response(self, response: Response) -> None:
        # Update matching request with status
        for evt in reversed(self._network_events):
            if evt.url == response.url and evt.status is None:
                evt.status = response.status
                break

    def _on_request_failed(self, request: Request) -> None:
        failure = request.failure
        failure_text = failure if isinstance(failure, str) else str(failure or "Request failed")
        self._failed_requests.append(
            FailedRequest(
                url=request.url,
                method=request.method,
                failure_text=failure_text,
            )
        )

    def _on_page_error(self, error: Exception) -> None:
        msg = str(error)
        stack = getattr(error, "stack", None)
        self._js_exceptions.append(
            JavaScriptException(
                message=msg,
                stack=stack,
            )
        )
        self._console_errors.append(f"[pageerror] {msg}")

    def _on_console(self, msg) -> None:
        text = msg.text
        level = msg.type
        location = str(msg.location) if msg.location else None
        self._console_messages.append(
            ConsoleMessage(
                level=level,
                text=text,
                location=location,
            )
        )
        if level in ("error", "warning"):
            self._console_errors.append(f"[{level}] {text}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_page(self) -> Page:
        if not self._initialized or self._page is None or self._page.is_closed():
            raise DriverError("WebTestDriver is not initialized. Call initialize() first.")
        return self._page


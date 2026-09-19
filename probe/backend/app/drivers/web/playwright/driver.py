"""
WebTestDriver — Playwright implementation of TestDriver.

This is the ONLY file in PROBE that imports Playwright.
PROBE Core must never import from this module directly;
it always works through the TestDriver ABC.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Request,
    Response,
    async_playwright,
)

from app.core.models import (
    Action,
    ActionType,
    ApplicationState,
    Bounds,
    Element,
    Evidence,
    EvidenceType,
    NetworkEvent,
    TestConfig,
    TestSession,
)
from app.drivers.common.base import TestDriver
from app.utils.errors import DriverError
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Directory for storing screenshots
SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "probe_data", "screenshots")


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
        self._console_errors: list[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Launch Playwright + Chromium and set up the browser context."""
        try:
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._config.headless,
            )
            self._context = await self._browser.new_context(
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                }
            )
            self._page = await self._context.new_page()

            # Network event capture
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            self._page.on("pageerror", self._on_page_error)
            self._page.on("console", self._on_console)

            self._initialized = True
            logger.info(
                "driver_initialized",
                component="WebTestDriver",
                test_id=self._session.id,
                event="playwright_ready",
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
            self._initialized = False

    async def reset_state(self) -> None:
        """Clear cookies, storage, and navigate to blank."""
        if not self._context:
            raise DriverError("Driver not initialized")
        await self._context.clear_cookies()
        if self._page:
            await self._page.goto("about:blank")
        self._network_events.clear()
        self._console_errors.clear()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> ApplicationState:
        page = self._require_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return await self.get_current_state()
        except Exception as exc:
            raise DriverError(f"Navigation failed to {url}: {exc}") from exc

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    async def get_current_state(self) -> ApplicationState:
        page = self._require_page()
        try:
            url = page.url
            title = await page.title()
            elements = await self.get_interactive_elements()
            network_snapshot = list(self._network_events)
            console_snapshot = list(self._console_errors)

            return ApplicationState(
                url=url,
                title=title,
                elements=elements,
                network_events=network_snapshot,
                console_errors=console_snapshot,
            )
        except Exception as exc:
            raise DriverError(f"Failed to capture state: {exc}") from exc

    async def get_interactive_elements(self) -> list[Element]:
        page = self._require_page()
        try:
            raw = await page.evaluate("""
                () => {
                    const selectors = [
                        'a[href]', 'button', 'input', 'select', 'textarea',
                        '[role="button"]', '[role="link"]', '[role="tab"]',
                        '[role="menuitem"]', '[onclick]', '[tabindex]'
                    ];
                    const seen = new Set();
                    const results = [];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => {
                            if (seen.has(el)) return;
                            seen.add(el);
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 && rect.height === 0) return;
                            const attrs = {};
                            for (const attr of el.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            results.push({
                                tag: el.tagName.toLowerCase(),
                                text: (el.textContent || '').trim().slice(0, 200),
                                selector: el.id ? '#' + el.id : el.className
                                    ? '.' + el.className.split(' ')[0]
                                    : el.tagName.toLowerCase(),
                                bounds: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                                is_interactive: true,
                                attributes: attrs,
                            });
                        });
                    });
                    return results.slice(0, 100);
                }
            """)
            return [Element(**item) for item in raw]
        except Exception as exc:
            logger.warning("get_elements_error", component="WebTestDriver", error=str(exc))
            return []

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
        if path is None:
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            path = os.path.join(SCREENSHOTS_DIR, f"{uuid.uuid4()}.png")
        try:
            await page.screenshot(path=path, full_page=False)
            return Evidence(
                type=EvidenceType.SCREENSHOT,
                screenshot_path=path,
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

    def _on_page_error(self, error: Exception) -> None:
        self._console_errors.append(str(error))

    def _on_console(self, msg) -> None:
        if msg.type in ("error", "warning"):
            self._console_errors.append(f"[{msg.type}] {msg.text}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_page(self) -> Page:
        if not self._initialized or self._page is None:
            raise DriverError("WebTestDriver is not initialized. Call initialize() first.")
        return self._page

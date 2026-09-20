"""
ExplorationEngine — Deterministic, autonomous web exploration engine for PROBE V1.

Implements the bounded exploration loop:
Open → Observe → Plan Safe Actions → Execute → Observe → Update State → Repeat
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
import urllib.parse
from typing import Any, Callable, Coroutine, Optional

from app.core.models import (
    Action,
    ActionResult,
    ActionType,
    AgentStatusState,
    AgentType,
    ApplicationState,
    BrowserActionEvent,
    Element,
    TestConfig,
    TestSession,
)
from app.drivers.common.base import TestDriver
from app.exploration.safety import SafetyPolicy, default_safety_policy
from app.utils.errors import DriverError
from app.utils.logging import get_logger

logger = get_logger(__name__)

EventCallback = Callable[[dict], Coroutine[Any, Any, None]]

MAX_VISITS_PER_URL = 3


class ExplorationEngine:
    """
    Autonomous, deterministic exploration engine.

    Maintains:
    - Exploration frontier & priority queue
    - Visited state fingerprints & state history
    - Action execution history & results
    - Loop detection and cycle avoidance
    - Bounded execution limits (actions, states, depth, duration)
    - Live multi-agent status tracking & browser interaction streaming
    """

    def __init__(
        self,
        driver: TestDriver,
        session: TestSession,
        safety_policy: Optional[SafetyPolicy] = None,
        event_callback: Optional[EventCallback] = None,
    ) -> None:
        self._driver = driver
        self._session = session
        self._config: TestConfig = session.config
        self._safety = safety_policy or default_safety_policy
        self._event_callback = event_callback

        # State & tracking
        self._visited_states: dict[str, ApplicationState] = {}  # fingerprint -> state
        self._visited_urls: set[str] = set()
        self._url_visit_counts: dict[str, int] = {}
        self._tried_actions_per_state: dict[str, set[str]] = {}  # fingerprint -> set(action_keys)
        self._executed_actions: list[ActionResult] = []
        self._all_observations: list[ApplicationState] = []
        self._current_depth = 0
        self._start_time: float = 0.0
        self._active_agent: AgentType = AgentType.TECHNICAL

    async def explore(self) -> tuple[list[ApplicationState], list[ActionResult]]:
        """
        Execute the bounded autonomous exploration loop.

        Returns:
            (all_observations, all_action_results)
        """
        self._start_time = time.perf_counter()
        logger.info(
            "exploration_engine_started",
            component="ExplorationEngine",
            test_id=self._session.id,
            url=self._session.url,
            max_actions=self._config.max_actions,
            max_states=self._config.max_states,
            max_depth=self._config.max_depth,
            max_duration=self._config.max_duration_seconds,
        )

        await self._emit("status", {
            "status": "running",
            "message": f"Opening {self._session.url}...",
        })
        await self._emit_agent_status(
            AgentType.TECHNICAL,
            f"Technical AI initializing browser and resolving {self._session.url}...",
        )

        # 1. Initial navigation & observation
        init_action = Action(
            type=ActionType.NAVIGATE,
            value=self._session.url,
            description=f"Initial navigation to {self._session.url}",
        )
        current_state = await self._driver.execute_action(init_action)

        # Capture screenshot for initial state
        try:
            ev = await self._driver.capture_screenshot()
            current_state.screenshot_path = ev.screenshot_path
        except Exception as exc:
            logger.warning("initial_screenshot_failed", error=str(exc))

        self._record_observation(current_state)

        # Emit initial observation events
        await self._emit("observation", self._state_event_payload(current_state))
        if current_state.screenshot_path:
            await self._emit("screenshot", {
                "url": f"/api/tests/{self._session.id}/screenshot",
                "path": current_state.screenshot_path,
            })
            await self._emit("browser_frame", {
                "url": f"/api/tests/{self._session.id}/screenshot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # If navigation encountered a fatal error, terminate early
        if current_state.error and not current_state.url:
            logger.warning("initial_navigation_failed", error=current_state.error)
            return self._all_observations, self._executed_actions

        # 2. Main Exploration Loop
        while not self._is_limits_reached():
            state_fp = current_state.fingerprint or current_state.url

            # Find next safe, untried action from current state
            next_action, target_element = self._select_next_action(current_state)

            if next_action is None:
                # No more untried actions in current state. Try backtracking if deep.
                if self._current_depth > 0:
                    back_action = Action(
                        type=ActionType.BACK,
                        description="Backtracking to previous page",
                    )
                    action_result, new_state = await self._execute_and_observe(
                        back_action, before_state=current_state, target_element=None
                    )
                    self._current_depth = max(0, self._current_depth - 1)
                    current_state = new_state
                    continue
                else:
                    logger.info("exploration_frontier_exhausted", test_id=self._session.id)
                    break

            # Mark action as tried for this state fingerprint
            action_key = self._action_signature(next_action, target_element)
            if state_fp not in self._tried_actions_per_state:
                self._tried_actions_per_state[state_fp] = set()
            self._tried_actions_per_state[state_fp].add(action_key)

            # Determine agent for action and emit agent status update if changed
            agent = self._determine_agent_for_action(next_action, target_element)
            if agent != self._active_agent:
                self._active_agent = agent
                await self._emit_agent_status(
                    agent,
                    f"{agent.value.replace('_', ' ').title()} AI executing {next_action.type.value.lower()} interaction...",
                )

            # Execute action with target element context
            action_result, new_state = await self._execute_and_observe(
                next_action, before_state=current_state, target_element=target_element
            )

            # Update depth tracking
            if next_action.type == ActionType.CLICK and new_state.url != current_state.url:
                self._current_depth += 1

            current_state = new_state

        elapsed = round(time.perf_counter() - self._start_time, 2)
        logger.info(
            "exploration_engine_completed",
            component="ExplorationEngine",
            test_id=self._session.id,
            duration_s=elapsed,
            total_actions=len(self._executed_actions),
            total_states=len(self._visited_states),
        )

        await self._emit_agent_status(
            AgentType.TECHNICAL,
            "Technical AI reviewing collected telemetry and analyzing findings...",
        )

        return self._all_observations, self._executed_actions

    # ------------------------------------------------------------------
    # Action Selection & Planning
    # ------------------------------------------------------------------

    def _select_next_action(
        self, state: ApplicationState
    ) -> tuple[Optional[Action], Optional[Element]]:
        """
        Deterministically select the highest-priority safe untried action.

        Priority Order:
        1. Navigation links (same origin)
        2. Buttons (click)
        3. Form inputs / Textareas / Checkboxes / Radios
        4. Select dropdowns
        5. Safe scrolling down
        """
        state_fp = state.fingerprint or state.url
        tried = self._tried_actions_per_state.get(state_fp, set())

        # Sort elements by category priority
        sorted_elements = self._prioritize_elements(state.elements)

        for elem in sorted_elements:
            if not elem.visible or not elem.enabled:
                continue

            action = self._create_action_for_element(elem, state)
            if action is None:
                continue

            action_key = self._action_signature(action, elem)
            if action_key in tried:
                continue

            # Verify safety policy
            is_safe, reason = self._safety.is_safe_action(
                action=action,
                element=elem,
                current_url=state.url,
                initial_url=self._session.url,
                allowed_domains=self._config.allowed_domains,
            )

            if not is_safe:
                logger.debug("action_skipped_safety", element=elem.text or elem.label, reason=reason)
                tried.add(action_key)
                continue

            # Check URL repetition if it's a link
            if elem.type == "link" and elem.attributes.get("href"):
                dest_href = elem.attributes["href"]
                normalized_dest = self._normalize_url(dest_href, state.url)
                if self._url_visit_counts.get(normalized_dest, 0) >= MAX_VISITS_PER_URL:
                    logger.debug("link_skipped_loop", url=normalized_dest)
                    tried.add(action_key)
                    continue

            return action, elem

        # If no element action was chosen, check if page is scrollable and not scrolled yet
        scroll_key = f"SCROLL:down"
        if scroll_key not in tried and state.page_dimensions and state.viewport:
            if state.page_dimensions.height > state.viewport.height + 150:
                tried.add(scroll_key)
                scroll_action = Action(
                    type=ActionType.SCROLL,
                    value="400",
                    description="Scroll down to reveal additional content",
                )
                return scroll_action, None

        return None, None

    def _prioritize_elements(self, elements: list[Element]) -> list[Element]:
        """
        Rank interactive elements:
        1. Links
        2. Buttons
        3. Inputs & Forms
        4. Selects
        5. Others
        """
        def rank(el: Element) -> int:
            t = el.type.lower()
            if t == "link":
                return 1
            if t == "button" or el.role == "button":
                return 2
            if t.startswith("input:") or t in ("textarea", "checkbox", "radio"):
                return 3
            if t == "select":
                return 4
            return 5

        return sorted(elements, key=rank)

    def _create_action_for_element(
        self, elem: Element, state: ApplicationState
    ) -> Optional[Action]:
        """Synthesize a platform-independent action from an Element."""
        target = elem.reference or elem.selector
        if not target:
            return None

        el_type = elem.type.lower()

        # Links & Buttons
        if el_type in ("link", "button", "checkbox", "radio") or elem.role in ("button", "link", "checkbox", "radio"):
            label_desc = elem.text or elem.label or target
            return Action(
                type=ActionType.CLICK,
                target=target,
                description=f"Click {el_type} '{label_desc}'",
                metadata={"element_id": elem.id, "type": el_type},
            )

        # Text inputs
        if el_type.startswith("input:") or el_type == "textarea":
            input_val = self._generate_sample_value(elem)
            label_desc = elem.label or elem.text or elem.attributes.get("placeholder") or target
            return Action(
                type=ActionType.TYPE,
                target=target,
                value=input_val,
                description=f"Type '{input_val}' into {el_type} '{label_desc}'",
                metadata={"element_id": elem.id, "type": el_type},
            )

        # Select dropdowns
        if el_type == "select":
            return Action(
                type=ActionType.CLICK,
                target=target,
                description=f"Click select dropdown '{elem.label or target}'",
                metadata={"element_id": elem.id, "type": el_type},
            )

        return None

    def _generate_sample_value(self, elem: Element) -> str:
        """Deterministic sample input based on element type and name."""
        t = elem.type.lower()
        name_lower = (elem.attributes.get("name") or elem.label or "").lower()

        if "email" in t or "email" in name_lower:
            return "tester@probe-test.org"
        if "password" in t or "pass" in name_lower:
            return "ProbePass123!"
        if "number" in t or "age" in name_lower or "qty" in name_lower:
            return "42"
        if "search" in t or "query" in name_lower or "q" == name_lower:
            return "sample query"
        if "tel" in t or "phone" in name_lower:
            return "555-0199"
        if "url" in t or "website" in name_lower:
            return "https://example.com"
        if "user" in name_lower or "name" in name_lower:
            return "ProbeTester"
        if t == "textarea" or "bio" in name_lower or "desc" in name_lower or "comment" in name_lower:
            return "Autonomous exploration sample text."

        return "Sample test data"

    def _determine_agent_for_action(
        self, action: Action, element: Optional[Element]
    ) -> AgentType:
        """Assign the appropriate AI agent role based on interaction context."""
        if action.type in (ActionType.NAVIGATE, ActionType.BACK):
            return AgentType.TECHNICAL
        if action.type == ActionType.SCROLL:
            return AgentType.UX_UI
        if action.type == ActionType.TYPE:
            return AgentType.USER_BEHAVIOR
        if action.type == ActionType.CLICK:
            if element and element.type in ("checkbox", "radio", "input:submit", "select"):
                return AgentType.USER_BEHAVIOR
            if element and "cart" in (element.text or "").lower() or "checkout" in (element.text or "").lower():
                return AgentType.USER_BEHAVIOR
            if element and element.type == "button":
                return AgentType.USER_BEHAVIOR
            return AgentType.TECHNICAL
        return AgentType.TECHNICAL

    async def _emit_agent_status(self, active_agent: AgentType, message: str) -> None:
        """Broadcast live multi-agent operational states."""
        await self._emit("agent_status", {
            "active_agent": active_agent.value,
            "agents": {
                "technical": "exploring" if active_agent == AgentType.TECHNICAL else "waiting",
                "user_behavior": "exploring" if active_agent == AgentType.USER_BEHAVIOR else "waiting",
                "ux_ui": "exploring" if active_agent == AgentType.UX_UI else "waiting",
                "chaos": "exploring" if active_agent == AgentType.CHAOS else "waiting",
            },
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Execution & Telemetry
    # ------------------------------------------------------------------

    async def _execute_and_observe(
        self,
        action: Action,
        before_state: ApplicationState,
        target_element: Optional[Element] = None,
    ) -> tuple[ActionResult, ApplicationState]:
        """Execute an action, measure duration, observe new state, and emit live inspection events."""
        act_start = time.perf_counter()
        before_fp = before_state.fingerprint
        agent = self._determine_agent_for_action(action, target_element)

        # 1. Resolve coordinates and bounding box for cursor & target visualization
        x: Optional[float] = None
        y: Optional[float] = None
        target_bounds_dict: Optional[dict] = None

        if target_element:
            bbox = target_element.bounding_box or target_element.bounds
            if bbox and bbox.width > 0 and bbox.height > 0:
                x = round(bbox.x + bbox.width / 2.0, 1)
                y = round(bbox.y + bbox.height / 2.0, 1)
                target_bounds_dict = {
                    "x": bbox.x,
                    "y": bbox.y,
                    "width": bbox.width,
                    "height": bbox.height,
                }

        if x is None and action.target and hasattr(self._driver, "get_element_coordinates"):
            try:
                coords = await self._driver.get_element_coordinates(action.target)
                if coords:
                    x = coords.get("x")
                    y = coords.get("y")
                    target_bounds_dict = {
                        "x": coords.get("left", (coords.get("x", 0) - coords.get("width", 0) / 2)),
                        "y": coords.get("top", (coords.get("y", 0) - coords.get("height", 0) / 2)),
                        "width": coords.get("width", 0),
                        "height": coords.get("height", 0),
                    }
            except Exception:
                pass

        # Fallback coordinates for scroll / navigation
        if x is None and y is None:
            if action.type == ActionType.SCROLL:
                x = 640.0
                y = 400.0
            elif action.type == ActionType.NAVIGATE:
                x = 640.0
                y = 80.0

        # Synthesize human-readable AI reason
        reason: str
        target_label = (
            (target_element.text or target_element.label) if target_element else (action.target or "page")
        )
        if action.type == ActionType.CLICK:
            reason = f"Interact with '{target_label}' to test navigation and state transitions"
        elif action.type == ActionType.TYPE:
            reason = f"Provide test data '{action.value}' into '{target_label}' to test input validation"
        elif action.type == ActionType.SCROLL:
            reason = "Scroll down to reveal lazy-loaded content and verify viewport stability"
        elif action.type == ActionType.BACK:
            reason = "Backtrack to previous application state to explore alternative pathways"
        else:
            reason = action.description or f"Execute {action.type.value} interaction"

        # Emit live BROWSER_ACTION event (drives real-time AI cursor animation & target highlight)
        await self._emit("browser_action", {
            "inspection_id": self._session.id,
            "agent": agent.value,
            "action": action.type.value.lower(),
            "phase": "targeting",
            "target": target_label,
            "selector": action.target,
            "x": x,
            "y": y,
            "target_bounds": target_bounds_dict,
            "value": action.value,
            "direction": "down" if action.type == ActionType.SCROLL else None,
            "amount": float(action.value or 400) if action.type == ActionType.SCROLL else None,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Emit ACTION_STARTED
        await self._emit("action_start", {
            "action_type": action.type.value,
            "target": action.target,
            "value": action.value,
            "agent": agent.value,
            "phase": "interacting",
            "x": x,
            "y": y,
            "target_bounds": target_bounds_dict,
            "description": action.description or f"Executing {action.type.value}",
        })

        # Micro-pause to allow smooth visual cursor travel, target box lock-on, and thought bubble rendering
        await asyncio.sleep(0.65)

        success = True
        error_msg: Optional[str] = None
        new_state: ApplicationState

        try:
            new_state = await self._driver.execute_action(action)
        except DriverError as exc:
            success = False
            error_msg = str(exc)
            new_state = before_state
            logger.warning("action_failed", action=action.type.value, target=action.target, error=error_msg)
        except Exception as exc:
            success = False
            error_msg = f"Unexpected action failure: {exc}"
            new_state = before_state
            logger.error("action_unexpected_failure", error=str(exc))

        duration_ms = round((time.perf_counter() - act_start) * 1000, 2)
        after_fp = new_state.fingerprint

        result = ActionResult(
            action=action,
            success=success,
            error=error_msg,
            duration_ms=duration_ms,
            before_state_fingerprint=before_fp,
            after_state_fingerprint=after_fp,
        )
        self._executed_actions.append(result)

        # Emit ACTION_COMPLETED or ACTION_FAILED
        if success:
            await self._emit("action_completed", {
                "action_type": action.type.value,
                "target": action.target,
                "agent": agent.value,
                "duration_ms": duration_ms,
                "description": action.description or f"Completed {action.type.value}",
                "new_url": new_state.url,
                "elements_count": len(new_state.elements),
            })
        else:
            await self._emit("action_failed", {
                "action_type": action.type.value,
                "target": action.target,
                "agent": agent.value,
                "error": error_msg,
                "description": f"Failed {action.type.value}: {error_msg}",
            })

        # Capture screenshot frame after interaction to ensure Live View is up to date
        try:
            ev = await self._driver.capture_screenshot()
            new_state.screenshot_path = ev.screenshot_path
            await self._emit("screenshot", {
                "url": f"/api/tests/{self._session.id}/screenshot",
                "path": new_state.screenshot_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await self._emit("browser_frame", {
                "url": f"/api/tests/{self._session.id}/screenshot",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.debug("interaction_screenshot_failed", error=str(exc))

        # Process new state if fingerprint is new or state changed
        if after_fp and after_fp not in self._visited_states:
            self._record_observation(new_state)
            await self._emit("observation", self._state_event_payload(new_state))

        return result, new_state

    # ------------------------------------------------------------------
    # Helpers & Bounds
    # ------------------------------------------------------------------

    def _record_observation(self, state: ApplicationState) -> None:
        fp = state.fingerprint or state.url
        self._visited_states[fp] = state
        self._all_observations.append(state)

        if state.url:
            self._visited_urls.add(state.url)
            norm_url = self._normalize_url(state.url)
            self._url_visit_counts[norm_url] = self._url_visit_counts.get(norm_url, 0) + 1

    def _is_limits_reached(self) -> bool:
        """Check all termination limits."""
        if len(self._executed_actions) >= self._config.max_actions:
            logger.info("max_actions_reached", count=len(self._executed_actions))
            return True
        if len(self._visited_states) >= self._config.max_states:
            logger.info("max_states_reached", count=len(self._visited_states))
            return True
        if self._current_depth >= self._config.max_depth:
            logger.info("max_depth_reached", depth=self._current_depth)
            return True
        if time.perf_counter() - self._start_time >= self._config.max_duration_seconds:
            logger.info("max_duration_reached")
            return True
        return False

    def _action_signature(self, action: Action, element: Optional[Element]) -> str:
        """Unique signature to avoid duplicate actions in the same state."""
        target = action.target or (element.reference if element else "")
        return f"{action.type.value}:{target}:{action.value or ''}"

    def _normalize_url(self, raw_url: str, base_url: str = "") -> str:
        try:
            full_url = urllib.parse.urljoin(base_url, raw_url) if base_url else raw_url
            parsed = urllib.parse.urlparse(full_url)
            return urllib.parse.urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                "",
                "",
            ))
        except Exception:
            return raw_url.lower().strip()

    def _state_event_payload(self, state: ApplicationState) -> dict:
        return {
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
        }

    async def _emit(self, event_type: str, data: dict) -> None:
        if self._event_callback:
            try:
                await self._event_callback({"type": event_type, **data})
            except Exception as exc:
                logger.warning("event_emit_failed", error=str(exc))

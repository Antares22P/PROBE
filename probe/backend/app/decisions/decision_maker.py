"""
DecisionMaker — decides the next action during exploration.

Uses heuristics in V1. Will use AIProvider in future versions.
"""
from __future__ import annotations

from app.core.models import Action, ActionType, ApplicationState, Element
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Elements to skip
SKIP_TAGS = {"script", "style", "meta", "link", "head"}


class DecisionMaker:
    """
    Decides the next exploration action based on the current application state.

    V1: simple heuristic — prefer links, then buttons.
    Future: use AIProvider for smarter decisions.
    """

    def __init__(self, test_id: str) -> None:
        self._test_id = test_id
        self._tried_elements: set[str] = set()

    def next_action(self, state: ApplicationState) -> Action | None:
        """
        Return the next action to take, or None if exploration is complete.
        """
        candidates = self._rank_elements(state.elements)

        for element in candidates:
            key = f"{element.tag}:{element.selector}:{element.text}"
            if key in self._tried_elements:
                continue
            self._tried_elements.add(key)

            if element.tag == "a" and element.attributes.get("href"):
                href = element.attributes["href"]
                if href.startswith("http") or href.startswith("/"):
                    return Action(
                        type=ActionType.CLICK,
                        target=element.selector,
                        metadata={"element_text": element.text, "href": href},
                    )

            if element.tag in ("button", "input") and element.attributes.get("type") != "password":
                return Action(
                    type=ActionType.CLICK,
                    target=element.selector,
                    metadata={"element_text": element.text},
                )

        return None

    def _rank_elements(self, elements: list[Element]) -> list[Element]:
        """Rank elements: links first, then buttons, then other interactive."""
        priority = {"a": 0, "button": 1, "input": 2}
        return sorted(
            [e for e in elements if e.tag not in SKIP_TAGS],
            key=lambda e: priority.get(e.tag, 99),
        )

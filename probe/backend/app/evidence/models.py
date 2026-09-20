"""
Structured Evidence models, Timeline, and Action Signatures for PROBE V1.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.models import Action, ActionType


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Evidence Enums & Models
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    SCREENSHOT = "screenshot"
    URL = "url"
    ACTION_SEQUENCE = "action_sequence"
    CONSOLE_ERROR = "console_error"
    JS_EXCEPTION = "js_exception"
    NETWORK_REQUEST = "network_request"
    HTTP_RESPONSE = "http_response"
    OBSERVATION = "observation"
    NAVIGATION_FAILURE = "navigation_failure"
    BLANK_PAGE = "blank_page"


class EvidenceItem(BaseModel):
    """A single piece of captured telemetry or artifact."""

    id: str = Field(default_factory=_uuid)
    type: EvidenceType
    timestamp: datetime = Field(default_factory=_now)
    url: Optional[str] = None
    status_code: Optional[int] = None
    method: Optional[str] = None
    message: Optional[str] = None
    stack: Optional[str] = None
    location: Optional[str] = None
    screenshot_path: Optional[str] = None
    action_sequence: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceTimeline(BaseModel):
    """An ordered chronological sequence of evidence items."""

    test_id: str
    finding_id: Optional[str] = None
    items: list[EvidenceItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Action Signature Helpers (Sufficient for Replay)
# ---------------------------------------------------------------------------


def format_action_signature(action: Action) -> str:
    """
    Format an Action into a deterministic, parseable signature string.

    Examples:
    - CLICK(#login-btn)
    - TYPE(#username, "admin")
    - NAVIGATE("https://example.com/login")
    - SCROLL(down, 300)
    - SELECT_OPTION(#country, "US")
    """
    atype = action.type.value.upper()
    target = action.target or ""
    value = action.value or ""

    if atype == "NAVIGATE":
        return f'NAVIGATE("{value}")'
    elif atype == "CLICK":
        return f"CLICK({target})"
    elif atype == "TYPE":
        # Escape quotes in value
        val_clean = value.replace('"', '\\"')
        return f'TYPE({target}, "{val_clean}")'
    elif atype == "SCROLL":
        direction = action.metadata.get("direction", "down")
        amount = action.metadata.get("amount", 300)
        return f"SCROLL({direction}, {amount})"
    elif atype == "SELECT_OPTION":
        val_clean = value.replace('"', '\\"')
        return f'SELECT_OPTION({target}, "{val_clean}")'
    elif atype == "HOVER":
        return f"HOVER({target})"
    elif atype == "SUBMIT":
        return f"SUBMIT({target})"
    elif atype == "WAIT":
        duration = action.metadata.get("duration_ms", 1000)
        return f"WAIT({duration})"
    else:
        return f"{atype}({target})"


def parse_action_signature(sig: str) -> Action:
    """
    Parse a signature string back into a structured Action model.
    """
    sig = sig.strip()
    match = re.match(r"^([A-Z_]+)\((.*)\)$", sig, re.DOTALL)
    if not match:
        return Action(type=ActionType.CLICK, target=sig, description=sig)

    atype_str, args_str = match.groups()
    args_str = args_str.strip()

    atype_upper = atype_str.upper()
    if atype_upper == "SELECT_OPTION":
        atype = ActionType.SELECT
    else:
        try:
            atype = ActionType(atype_upper)
        except ValueError:
            atype = ActionType.CLICK

    if atype == ActionType.NAVIGATE:
        url_val = args_str.strip('"\'')
        return Action(
            type=ActionType.NAVIGATE,
            value=url_val,
            description=f"Navigate to {url_val}",
        )

    if atype == ActionType.CLICK:
        target = args_str
        return Action(
            type=ActionType.CLICK,
            target=target,
            description=f"Click on {target}",
        )

    if atype == ActionType.TYPE:
        # Expected format: selector, "text"
        parts = args_str.split(",", 1)
        target = parts[0].strip()
        val = parts[1].strip().strip('"\'') if len(parts) > 1 else ""
        return Action(
            type=ActionType.TYPE,
            target=target,
            value=val,
            description=f"Type '{val}' into {target}",
        )

    if atype == ActionType.SCROLL:
        parts = [p.strip() for p in args_str.split(",")]
        direction = parts[0] if len(parts) > 0 else "down"
        amount = float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "", 1).isdigit() else 300.0
        return Action(
            type=ActionType.SCROLL,
            description=f"Scroll {direction} {amount}px",
            metadata={"direction": direction, "amount": amount},
        )

    if atype == ActionType.SELECT:
        parts = args_str.split(",", 1)
        target = parts[0].strip()
        val = parts[1].strip().strip('"\'') if len(parts) > 1 else ""
        return Action(
            type=ActionType.SELECT,
            target=target,
            value=val,
            description=f"Select option '{val}' on {target}",
        )

    if atype == ActionType.WAIT:
        dur = float(args_str) if args_str.isdigit() else 1000.0
        return Action(
            type=ActionType.WAIT,
            description=f"Wait {dur}ms",
            metadata={"duration_ms": dur},
        )

    return Action(type=atype, target=args_str, description=f"{atype_str} on {args_str}")

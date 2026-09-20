"""
Universal platform-independent models for PROBE.

These models are NOT web-specific. They are the lingua franca between
PROBE Core, TestDrivers, exploration, detection, findings, and reproduction.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PlatformType(str, Enum):
    """Supported test platforms."""

    WEB = "web"
    ANDROID = "android"
    IOS = "ios"


class TestStatus(str, Enum):
    """Lifecycle states of a TestSession."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionType(str, Enum):
    """All action types supported across platforms."""

    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    TYPE = "TYPE"
    SELECT = "SELECT"
    SCROLL = "SCROLL"
    SWIPE = "SWIPE"
    BACK = "BACK"
    WAIT = "WAIT"
    SCREENSHOT = "SCREENSHOT"


import hashlib
import urllib.parse


# ---------------------------------------------------------------------------
# Dimensions & Viewport
# ---------------------------------------------------------------------------


class Dimensions(BaseModel):
    """Dimensions of a webpage or screen."""

    width: float = 0.0
    height: float = 0.0


class Viewport(BaseModel):
    """Browser or device viewport size."""

    width: int = 1280
    height: int = 720


# ---------------------------------------------------------------------------
# Element
# ---------------------------------------------------------------------------


class Bounds(BaseModel):
    """Screen bounds of a UI element."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class Element(BaseModel):
    """A platform-independent UI element."""

    id: str = Field(default_factory=_uuid)
    tag: str = ""
    type: str = ""  # link, button, input:text, textarea, select, checkbox, radio, form, etc.
    role: str = ""  # ARIA role or semantic role
    text: str = ""
    label: str = ""
    reference: str = ""  # CSS selector, XPath, or stable locator
    selector: str = ""  # Backward-compatible selector alias
    visible: bool = True
    enabled: bool = True
    bounding_box: Optional[Bounds] = None
    bounds: Optional[Bounds] = None  # Backward-compatible bounds alias
    is_interactive: bool = True
    attributes: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signals & Logs
# ---------------------------------------------------------------------------


class ConsoleMessage(BaseModel):
    """A captured browser console message."""

    id: str = Field(default_factory=_uuid)
    level: str = "log"  # log, info, warn, error, debug
    text: str = ""
    location: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)


class JavaScriptException(BaseModel):
    """An uncaught JavaScript exception (pageerror)."""

    id: str = Field(default_factory=_uuid)
    message: str = ""
    stack: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)


class FailedRequest(BaseModel):
    """A network request that failed."""

    id: str = Field(default_factory=_uuid)
    url: str = ""
    method: str = "GET"
    failure_text: str = ""
    status: Optional[int] = None
    timestamp: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class Action(BaseModel):
    """A single action taken during a test."""

    id: str = Field(default_factory=_uuid)
    type: ActionType
    target: Optional[str] = None  # selector or element id
    value: Optional[str] = None  # e.g. text to type, URL to navigate
    timestamp: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class EvidenceType(str, Enum):
    SCREENSHOT = "screenshot"
    LOG = "log"
    NETWORK_EVENT = "network_event"
    CONSOLE_ERROR = "console_error"
    DOM_SNAPSHOT = "dom_snapshot"


class Evidence(BaseModel):
    """Captured evidence during a test."""

    id: str = Field(default_factory=_uuid)
    type: EvidenceType
    content: Optional[str] = None  # text content or path
    screenshot_path: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# ApplicationState & Fingerprinting
# ---------------------------------------------------------------------------


class NetworkEvent(BaseModel):
    """A captured network request/response."""

    url: str
    method: str = "GET"
    status: Optional[int] = None
    timestamp: datetime = Field(default_factory=_now)
    duration_ms: Optional[float] = None
    error: Optional[str] = None


def compute_state_fingerprint(
    url: str,
    title: str,
    elements: list[Element],
    visible_text: str = "",
) -> str:
    """
    Generate a deterministic SHA-256 state fingerprint based on:
    - Normalized URL (scheme, host, path, sorted query parameters, stripped fragment)
    - Normalized page title
    - Sorted interactive elements signature (type, role, text, label, reference)
    - Text prefix
    """
    try:
        parsed = urllib.parse.urlparse(url.strip())
        qs = urllib.parse.parse_qsl(parsed.query)
        sorted_qs = urllib.parse.urlencode(sorted(qs))
        normalized_url = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            sorted_qs,
            "",
        ))
    except Exception:
        normalized_url = url.strip().lower()

    norm_title = (title or "").strip().lower()

    # Sort element signatures
    elem_signatures = []
    for elem in elements:
        sig = f"{elem.type}|{elem.role}|{elem.text.strip()}|{elem.label.strip()}|{elem.reference.strip()}"
        elem_signatures.append(sig)
    elem_signatures.sort()

    text_sample = (visible_text or "").strip()[:1000]

    raw_payload = "\n".join([
        f"URL:{normalized_url}",
        f"TITLE:{norm_title}",
        f"ELEMENTS:{'|'.join(elem_signatures)}",
        f"TEXT:{text_sample}",
    ])

    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


class ApplicationState(BaseModel):
    """A platform-independent snapshot of application state."""

    id: str = Field(default_factory=_uuid)
    url: str = ""
    requested_url: str = ""
    title: str = ""
    visible_text: str = ""
    viewport: Optional[Viewport] = None
    page_dimensions: Optional[Dimensions] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    elements: list[Element] = Field(default_factory=list)
    console_messages: list[ConsoleMessage] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
    js_exceptions: list[JavaScriptException] = Field(default_factory=list)
    failed_requests: list[FailedRequest] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    fingerprint: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)
    platform: PlatformType = PlatformType.WEB
    raw_metadata: dict[str, Any] = Field(default_factory=dict)



# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


class Observation(BaseModel):
    """A recorded observation at a point in time."""

    id: str = Field(default_factory=_uuid)
    state: ApplicationState
    actions_taken: list[Action] = Field(default_factory=list)
    findings_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# TestSession
# ---------------------------------------------------------------------------


class TestConfig(BaseModel):
    """Configuration for a test run."""

    max_actions: int = 50
    max_depth: int = 3
    timeout_seconds: int = 300
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720


class TestSession(BaseModel):
    """The root model for a PROBE test run."""

    id: str = Field(default_factory=_uuid)
    url: str
    platform: PlatformType = PlatformType.WEB
    status: TestStatus = TestStatus.PENDING
    config: TestConfig = Field(default_factory=TestConfig)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    observations: list[Observation] = Field(default_factory=list)

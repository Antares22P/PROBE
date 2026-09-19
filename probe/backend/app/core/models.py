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
    text: str = ""
    selector: str = ""
    bounds: Optional[Bounds] = None
    is_interactive: bool = False
    attributes: dict[str, str] = Field(default_factory=dict)


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
# ApplicationState
# ---------------------------------------------------------------------------


class NetworkEvent(BaseModel):
    """A captured network request/response."""

    url: str
    method: str = "GET"
    status: Optional[int] = None
    timestamp: datetime = Field(default_factory=_now)
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class ApplicationState(BaseModel):
    """A platform-independent snapshot of application state."""

    id: str = Field(default_factory=_uuid)
    url: str = ""
    title: str = ""
    screenshot_path: Optional[str] = None
    elements: list[Element] = Field(default_factory=list)
    network_events: list[NetworkEvent] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
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

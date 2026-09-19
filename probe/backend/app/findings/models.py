"""
Finding model for PROBE.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """A detected problem in the tested application."""

    id: str = Field(default_factory=_uuid)
    test_id: str
    severity: FindingSeverity = FindingSeverity.INFO
    category: str = "general"
    title: str
    description: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)

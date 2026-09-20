"""
Reproduction models and statuses for PROBE V1.
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


class ReproductionStatus(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    REPRODUCING = "reproducing"
    REPRODUCED = "reproduced"
    NOT_REPRODUCED = "not_reproduced"
    INTERMITTENT = "intermittent"
    FAILED = "failed"


class AttemptRecord(BaseModel):
    """Result of a single reproduction attempt."""

    attempt_number: int
    reproduced: bool
    duration_ms: float = 0.0
    error: Optional[str] = None
    fresh_signals_count: int = 0
    fresh_fingerprints: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_now)


class ReproductionResult(BaseModel):
    """The overall outcome of a reproduction run."""

    id: str = Field(default_factory=_uuid)
    test_id: str
    finding_id: str
    status: ReproductionStatus = ReproductionStatus.NOT_ATTEMPTED
    attempts: int = 1
    successful_attempts: int = 0
    action_sequence: list[str] = Field(default_factory=list)
    fresh_evidence: list[dict[str, Any]] = Field(default_factory=list)
    attempt_records: list[AttemptRecord] = Field(default_factory=list)
    error_message: Optional[str] = None
    started_at: datetime = Field(default_factory=_now)
    completed_at: Optional[datetime] = None

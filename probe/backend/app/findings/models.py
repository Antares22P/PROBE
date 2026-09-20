"""
Structured Finding model, categories, severities, statuses, and fingerprinting for PROBE V1.
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse
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


class FindingCategory(str, Enum):
    FUNCTIONAL = "functional"
    NETWORK = "network"
    JAVASCRIPT = "javascript"
    CRASH = "crash"
    PERFORMANCE = "performance"
    UI = "ui"
    UX = "ux"
    SECURITY = "security"
    ACCESSIBILITY = "accessibility"
    OTHER = "other"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    POTENTIAL = "potential"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    DISMISSED = "dismissed"


# ---------------------------------------------------------------------------
# Finding Fingerprint Function
# ---------------------------------------------------------------------------


def compute_finding_fingerprint(
    category: str,
    error_type: str,
    target_url: str,
    signature: str,
) -> str:
    """
    Generate a stable, deterministic fingerprint to deduplicate repeated findings.

    Normalizes:
    - URL (stripping dynamic query params, timestamps, hash fragments)
    - Signature (stripping line/col numbers, memory addresses, timestamps)
    """
    try:
        parsed = urllib.parse.urlparse(target_url.strip())
        norm_url = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        ))
    except Exception:
        norm_url = target_url.strip().lower()

    # Normalize error signature by stripping dynamic numbers/addresses
    cleaned_sig = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", signature)
    cleaned_sig = re.sub(r":\d+:\d+", ":LINE:COL", cleaned_sig)
    cleaned_sig = re.sub(r"\b\d{10,}\b", "TIMESTAMP", cleaned_sig)
    cleaned_sig = cleaned_sig.strip().lower()

    raw_payload = f"{category.lower()}|{error_type.lower()}|{norm_url}|{cleaned_sig}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Finding Model
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    """A detected problem in the tested application."""

    id: str = Field(default_factory=_uuid)
    test_id: str
    title: str
    category: FindingCategory = FindingCategory.OTHER
    severity: FindingSeverity = FindingSeverity.MEDIUM
    status: FindingStatus = FindingStatus.POTENTIAL
    confidence: float = 0.8
    description: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reproduction: Optional[dict[str, Any]] = None
    recommendation: Optional[str] = None
    ai_analysis: Optional[dict[str, Any]] = None
    fingerprint: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)
    created_at: datetime = Field(default_factory=_now)

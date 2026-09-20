"""
Pydantic schemas for AI reasoning, structured findings analysis, and error classification.
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


class AIErrorType(str, Enum):
    UNAVAILABLE = "AI unavailable"
    TIMEOUT = "AI timeout"
    INVALID_RESPONSE = "AI invalid response"
    QUOTA_EXCEEDED = "AI quota/rate limit"
    UNCONFIGURED = "AI unconfigured"
    UNKNOWN = "AI unknown error"


class AIError(BaseModel):
    """Structured error information when AI analysis fails."""

    error_type: AIErrorType
    message: str
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=_now)


class FindingAnalysisResult(BaseModel):
    """
    Structured AI output for finding analysis.
    Distinguishes observed facts from hypotheses and uncertainty.
    """

    id: str = Field(default_factory=_uuid)
    is_meaningful: bool = Field(
        default=True,
        description="Whether this finding represents a genuine application issue vs benign/ignorable noise",
    )
    category: str = Field(
        default="other",
        description="Refined categorization (e.g., functional, network, javascript, crash, ui, ux, security, performance)",
    )
    severity_suggestion: str = Field(
        default="medium",
        description="Suggested severity rating: low, medium, high, critical",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence in this analysis between 0.0 and 1.0",
    )

    # Fact vs Hypothesis separation
    observed_facts: list[str] = Field(
        default_factory=list,
        description="Concrete, verifiable empirical facts observed in telemetry, logs, or reproduction steps",
    )
    hypotheses: list[str] = Field(
        default_factory=list,
        description="Plausible hypotheses explaining what caused the observed behavior",
    )
    uncertainty: str = Field(
        default="",
        description="Explicit statement of what is unknown, ambiguous, or unverifiable without further evidence",
    )

    explanation: str = Field(
        default="",
        description="Clear, concise summary explaining what went wrong and how it impacts the user experience",
    )
    possible_cause: str = Field(
        default="",
        description="Likely architectural, code, network, or configuration root cause",
    )
    recommendation: str = Field(
        default="",
        description="Actionable remediation guidance for developers or QA engineers",
    )
    investigation_suggestion: str = Field(
        default="",
        description="Concrete next steps or manual verification tests to confirm root cause",
    )

    error: Optional[AIError] = None
    model_name: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=_now)


class TestSummaryAnalysis(BaseModel):
    """
    High-level test run summary analysis from AI.
    """

    overall_health: str = Field(
        default="healthy",
        description="General state: healthy, degraded, critical_issues_found",
    )
    key_takeaways: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    error: Optional[AIError] = None
    model_name: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=_now)

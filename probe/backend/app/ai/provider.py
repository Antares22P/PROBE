"""
AIProvider — abstract base class for AI integrations in PROBE.

The Core depends strictly on this interface. Concrete implementations
(e.g., GeminiProvider, NullProvider) handle model-specific APIs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel

from app.ai.schemas.finding_analysis import FindingAnalysisResult, TestSummaryAnalysis
from app.findings.models import Finding


class AIRequest(BaseModel):
    """Input to an AI provider."""

    prompt: str
    context: dict[str, Any] = {}
    max_tokens: int = 2048
    temperature: float = 0.2


class AIResponse(BaseModel):
    """Output from an AI provider."""

    content: str
    model: str
    tokens_used: int = 0
    raw: dict[str, Any] = {}


class AIProvider(ABC):
    """
    Abstract AI provider interface.

    Implementations:
        - GeminiProvider  (probe.backend.app.ai.providers.gemini_provider)
        - NullProvider    (probe.backend.app.ai.providers.null_provider)
    """

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Generate a raw text response for the given request."""
        ...

    @abstractmethod
    async def analyze_finding(
        self,
        finding: Finding,
        evidence_context: Optional[dict[str, Any]] = None,
    ) -> FindingAnalysisResult:
        """
        Analyze a structured finding and return structured AI reasoning.
        Must not crash if the provider is unavailable or fails.
        """
        ...

    @abstractmethod
    async def generate_test_summary(
        self,
        findings: list[Finding],
        test_summary: dict[str, Any],
    ) -> TestSummaryAnalysis:
        """
        Analyze all findings from a test session and produce a high-level summary.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and ready."""
        ...

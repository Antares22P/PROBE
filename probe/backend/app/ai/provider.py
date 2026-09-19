"""
AIProvider — abstract base class for AI integrations.

Create a concrete provider (e.g., GeminiProvider) by subclassing AIProvider.
V1 ships with NullProvider only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel


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
        - NullProvider  (probe.backend.app.ai.providers.null_provider) — no-op
        - GeminiProvider  (future)
    """

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Generate a response for the given request."""
        ...

    @abstractmethod
    async def analyze_findings(self, findings: list[dict], context: dict) -> str:
        """Analyze a list of findings and return a structured report."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and available."""
        ...

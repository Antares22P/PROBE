"""
NullProvider — no-op AIProvider implementation.

Returns empty/placeholder responses. Used until a real AI provider
(e.g., GeminiProvider) is integrated.
"""
from __future__ import annotations

from app.ai.provider import AIProvider, AIRequest, AIResponse


class NullProvider(AIProvider):
    """
    No-op AI provider. Returns empty responses.

    Replace this with GeminiProvider when integrating Gemini.
    """

    async def generate(self, request: AIRequest) -> AIResponse:
        return AIResponse(
            content="[AI analysis not yet integrated]",
            model="null",
            tokens_used=0,
        )

    async def analyze_findings(self, findings: list[dict], context: dict) -> str:
        return "[AI analysis not yet integrated — configure an AIProvider]"

    @property
    def provider_name(self) -> str:
        return "NullProvider"

    @property
    def is_available(self) -> bool:
        return False

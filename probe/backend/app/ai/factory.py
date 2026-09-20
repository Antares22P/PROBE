"""
AIProvider Factory — Instantiates the appropriate AI provider based on environment configuration.
"""
from __future__ import annotations

import os
from typing import Optional

from app.ai.provider import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.null_provider import NullProvider

_cached_provider: Optional[AIProvider] = None


def get_ai_provider(force_refresh: bool = False) -> AIProvider:
    """
    Get the configured AIProvider instance.
    If GEMINI_API_KEY is present, initializes GeminiProvider; otherwise falls back to NullProvider.
    """
    global _cached_provider

    if _cached_provider is not None and not force_refresh:
        return _cached_provider

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if api_key:
        provider = GeminiProvider(api_key=api_key)
        _cached_provider = provider
        return provider

    provider = NullProvider()
    _cached_provider = provider
    return provider


def set_ai_provider(provider: Optional[AIProvider]) -> None:
    """Set or override the global AI provider instance (useful for testing)."""
    global _cached_provider
    _cached_provider = provider

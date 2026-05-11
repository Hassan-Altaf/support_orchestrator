"""LLM provider package.

Re-exports the public surface and provides the `get_llm_provider` factory
that maps `Settings.llm_provider` to a concrete instance.
"""

from __future__ import annotations

from app.config import Settings
from app.llm.anthropic_provider import AnthropicProvider, AnthropicProviderError
from app.llm.gemini_provider import GeminiProvider, GeminiProviderError
from app.llm.mock_provider import MockProvider
from app.llm.openai_provider import OpenAIProvider, OpenAIProviderError
from app.llm.provider import LLMProvider, call_with_retry
from app.llm.recording_provider import RecordingProvider, RecordingProviderError

__all__ = [
    "AnthropicProvider",
    "AnthropicProviderError",
    "GeminiProvider",
    "GeminiProviderError",
    "LLMProvider",
    "MockProvider",
    "OpenAIProvider",
    "OpenAIProviderError",
    "RecordingProvider",
    "RecordingProviderError",
    "call_with_retry",
    "get_llm_provider",
]


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Construct the configured LLMProvider for this Settings instance."""
    match settings.llm_provider:
        case "openai":
            return OpenAIProvider(settings)
        case "anthropic":
            return AnthropicProvider(settings)
        case "gemini":
            return GeminiProvider(settings)
        case "mock":
            return MockProvider()
        case _:  # pragma: no cover — Literal guards this at type-check time
            raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")

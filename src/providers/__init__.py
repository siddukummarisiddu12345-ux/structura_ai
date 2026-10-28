"""Provider registry. Add new providers here."""
from __future__ import annotations

from .base import LLMProvider, ProviderAuthError, ProviderError
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider

PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}
PROVIDER_LABELS: dict[str, str] = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
}


def create_provider(name: str, api_key: str | None) -> LLMProvider:
    """Instantiate a provider by name."""
    try:
        provider_class = PROVIDER_CLASSES[name]
    except KeyError:
        raise ProviderError(f"Unknown provider '{name}'.") from None
    return provider_class(api_key)  # type: ignore[call-arg]


__all__ = [
    "LLMProvider", "ProviderAuthError", "ProviderError", "PROVIDER_CLASSES",
    "PROVIDER_LABELS", "create_provider",
]
"""Provider implementations for Structura AI."""

from src.providers.base import ProviderError
from src.providers.gemini_provider import GeminiProvider
from src.providers.openai_provider import OpenAIProvider

PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
}


def create_provider(provider_name, settings):
    name = provider_name.lower()

    if name == "gemini":
        return GeminiProvider(settings)
    if name == "openai":
        return OpenAIProvider(settings)

    raise ValueError(f"Unsupported provider: {provider_name}")
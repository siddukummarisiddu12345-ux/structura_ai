"""Shared provider interface and error types.

To add a provider: subclass LLMProvider, implement ``generate`` (translate SDK
errors into the ProviderError classes below), then register it in
``src/providers/__init__.py`` and ``src/config.py``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Base class for provider failures. Messages must never contain secrets."""

    kind = "provider_error"


class ProviderAuthError(ProviderError):
    """The API key is missing, invalid, or not allowed to use the model."""

    kind = "provider_auth"


class ProviderRateLimitError(ProviderError):
    """The provider rejected the request because of rate or quota limits."""

    kind = "provider_rate_limit"


class ProviderUnavailableError(ProviderError):
    """The provider could not be reached or had a server-side problem."""

    kind = "provider_unavailable"


class LLMProvider(ABC):
    """Minimal interface every provider implements."""

    name: str = "base"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, model: str) -> str:
        """Send the prompts to ``model`` and return the raw text reply.

        Raises a ProviderError subclass on any failure.
        """

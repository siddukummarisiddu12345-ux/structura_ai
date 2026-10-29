"""Base provider abstract class and custom provider exceptions."""

from __future__ import annotations
from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class ProviderUnavailableError(ProviderError):
    """Raised when the LLM provider cannot be reached."""
    def __init__(self, message: str) -> None:
        super().__init__("provider_unavailable", message)


class ProviderAuthError(ProviderError):
    """Raised when provider authentication fails."""
    def __init__(self, message: str) -> None:
        super().__init__("provider_auth_error", message)


class ProviderRateLimitError(ProviderError):
    """Raised when the LLM provider rate limit is exceeded."""
    def __init__(self, message: str) -> None:
        super().__init__("provider_rate_limit", message)


class BaseProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, model: str) -> str:
        """Generate a response given system and user prompts."""
        pass


# Alias to support imports expecting LLMProvider
LLMProvider = BaseProvider

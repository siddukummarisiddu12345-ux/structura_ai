"""OpenAI provider (openai SDK, Chat Completions). All OpenAI-specific code lives here."""
from __future__ import annotations

from .base import (
    LLMProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

REQUEST_TIMEOUT_SECONDS = 60.0


class OpenAIProvider(LLMProvider):
    """Calls OpenAI chat models in JSON mode."""

    name = "openai"

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ProviderAuthError("No OpenAI API key is configured (set OPENAI_API_KEY).")
        try:
            import openai
        except ImportError as exc:
            raise ProviderError(
                "The 'openai' package is not installed. Run: pip install -r requirements.txt"
            ) from exc
        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=2)

    def generate(self, system_prompt: str, user_prompt: str, model: str) -> str:
        openai = self._openai
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError):
            raise ProviderAuthError("OpenAI rejected the API key. Check OPENAI_API_KEY.") from None
        except openai.RateLimitError:
            raise ProviderRateLimitError(
                "OpenAI rate limit or quota reached. Wait, or check your plan and billing."
            ) from None
        except openai.APIConnectionError:
            raise ProviderUnavailableError(
                "Could not reach OpenAI. Check your connection and try again."
            ) from None
        except openai.NotFoundError:
            raise ProviderError("OpenAI could not find that model (HTTP 404). Check the model name.") from None
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise ProviderUnavailableError(
                    f"OpenAI service error (HTTP {exc.status_code}). Try again later."
                ) from None
            raise ProviderError(f"OpenAI request failed (HTTP {exc.status_code}).") from None
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed unexpectedly ({type(exc).__name__}).") from None

        choices = getattr(response, "choices", None) or []
        content = choices[0].message.content if choices else None
        if not content:
            raise ProviderError("OpenAI returned an empty response.")
        return content

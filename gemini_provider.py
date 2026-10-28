"""Google Gemini provider (google-genai SDK). All Gemini-specific code lives here."""
from __future__ import annotations

from .base import (
    LLMProvider,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

REQUEST_TIMEOUT_MS = 60_000


class GeminiProvider(LLMProvider):
    """Calls Gemini models and asks for a JSON response."""

    name = "gemini"

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ProviderAuthError("No Gemini API key is configured (set GEMINI_API_KEY).")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderError(
                "The 'google-genai' package is not installed. Run: pip install -r requirements.txt"
            ) from exc
        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS)
        )

    def generate(self, system_prompt: str, user_prompt: str, model: str) -> str:
        from google.genai import errors

        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
        )
        try:
            response = self._client.models.generate_content(
                model=model, contents=user_prompt, config=config
            )
        except errors.APIError as exc:
            raise _translate_api_error(exc) from None
        except Exception as exc:  # network problems, timeouts, SDK bugs
            raise ProviderUnavailableError(
                f"Could not reach Gemini ({type(exc).__name__}). Check your connection and try again."
            ) from None
        text = getattr(response, "text", None)
        if not text:
            raise ProviderError("Gemini returned no text (the response may have been blocked).")
        return text


def _translate_api_error(exc: Exception) -> ProviderError:
    """Map a Gemini APIError to our error types without echoing raw messages."""
    code = getattr(exc, "code", None)
    detail = str(exc).lower()
    if code in (401, 403) or (code == 400 and "api key" in detail):
        return ProviderAuthError("Gemini rejected the API key. Check GEMINI_API_KEY.")
    if code == 429:
        return ProviderRateLimitError("Gemini rate limit or quota reached. Wait and try again.")
    if isinstance(code, int) and code >= 500:
        return ProviderUnavailableError(f"Gemini service error (HTTP {code}). Try again later.")
    if code == 404:
        return ProviderError("Gemini could not find that model (HTTP 404). Check the model name.")
    return ProviderError(f"Gemini request failed (HTTP {code}).")

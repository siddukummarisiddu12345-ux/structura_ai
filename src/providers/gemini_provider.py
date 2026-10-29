"""Gemini LLM provider implementation."""

from __future__ import annotations

import os
from google import genai
from google.genai import errors
from src.providers.base import BaseProvider, ProviderError, ProviderUnavailableError

class GeminiProvider(BaseProvider):
    """Google Gemini LLM provider using the official google-genai SDK."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ProviderError("auth_error", "Gemini API key is missing.")

        self.client = genai.Client(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str, model: str) -> str:
        """Generate text content using Gemini."""
        model_name = model.strip() if model else ""
        if not model_name:
            model_name = "gemini-3.8-flash"  # Active model fallback

        try:
            full_prompt = f"System Instructions:\n{system_prompt}\n\nUser Document:\n{user_prompt}"

            response = self.client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )

            if not response or not response.text:
                raise ProviderError("empty_response", "Received empty response from Gemini.")
            return response.text

        except errors.APIError as exc:
            raise _translate_api_error(exc) from None
        except Exception as exc:
            raise ProviderUnavailableError(f"Could not reach Gemini ({type(exc).__name__}).") from exc

def _translate_api_error(exc: errors.APIError) -> ProviderError:
    code = getattr(exc, "code", 400)
    message = str(exc)
    if code == 401 or "API key not valid" in message:
        raise ProviderError("auth_error", "Invalid Gemini API key.")
    if code == 429 or "Resource has been exhausted" in message:
        raise ProviderError("rate_limit", "Gemini rate limit exceeded.")
    return ProviderError("provider_error", f"Gemini API error: {message}")

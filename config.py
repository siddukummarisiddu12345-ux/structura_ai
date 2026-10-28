"""Configuration loaded from environment variables (and an optional .env file).

API keys are only ever read from the environment. They are never written to
logs, the UI, or generated files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# provider name -> environment variable holding its API key
PROVIDER_ENV_VARS: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

# provider name -> (environment variable for the model list, defaults)
# Model names change over time; override them in .env if these are retired.
PROVIDER_MODEL_SETTINGS: dict[str, tuple[str, tuple[str, ...]]] = {
    "gemini": ("GEMINI_MODELS", ("gemini-2.5-flash", "gemini-2.5-flash-lite")),
    "openai": ("OPENAI_MODELS", ("gpt-4o-mini", "gpt-4.1-mini")),
}

DEFAULT_MAX_INPUT_CHARS = 20_000
HARD_MAX_INPUT_CHARS = 100_000
DEFAULT_MAX_RETRIES = 1
HARD_MAX_RETRIES = 3

_PLACEHOLDER_PREFIXES = ("your-", "your_", "changeme", "<")


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    api_keys: dict[str, str | None] = field(default_factory=dict, repr=False)
    models: dict[str, tuple[str, ...]] = field(default_factory=dict)
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    max_retries: int = DEFAULT_MAX_RETRIES

    def api_key_for(self, provider: str) -> str | None:
        """Return the API key for a provider, or None if not configured."""
        return self.api_keys.get(provider)

    def models_for(self, provider: str) -> tuple[str, ...]:
        """Return the selectable models for a provider."""
        return self.models.get(provider, ())

    def is_configured(self, provider: str) -> bool:
        """True when a real (non-placeholder) key is available."""
        return bool(self.api_key_for(provider))

    def secrets(self) -> list[str]:
        """All configured key values, used only to redact error messages."""
        return [key for key in self.api_keys.values() if key]


def _clean_key(value: str | None) -> str | None:
    """Treat empty values and .env.example placeholders as 'not configured'."""
    if value is None:
        return None
    value = value.strip().strip('"').strip("'")
    if not value or value.lower().startswith(_PLACEHOLDER_PREFIXES):
        return None
    return value


def _parse_list(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse a comma-separated list, falling back to the default if empty."""
    if not value:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _parse_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    """Parse an integer setting and clamp it into [minimum, maximum]."""
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))


def load_settings() -> Settings:
    """Read settings from the environment, loading .env first if present."""
    load_dotenv(override=False)
    api_keys = {
        provider: _clean_key(os.getenv(env_var))
        for provider, env_var in PROVIDER_ENV_VARS.items()
    }
    models = {
        provider: _parse_list(os.getenv(env_var), defaults)
        for provider, (env_var, defaults) in PROVIDER_MODEL_SETTINGS.items()
    }
    return Settings(
        api_keys=api_keys,
        models=models,
        max_input_chars=_parse_int(
            os.getenv("MAX_INPUT_CHARS"), DEFAULT_MAX_INPUT_CHARS, 500, HARD_MAX_INPUT_CHARS
        ),
        max_retries=_parse_int(
            os.getenv("MAX_RETRIES"), DEFAULT_MAX_RETRIES, 0, HARD_MAX_RETRIES
        ),
    )

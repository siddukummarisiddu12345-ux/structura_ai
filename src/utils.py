"""Utility helper functions and custom exceptions for the application."""

from __future__ import annotations


class InputValidationError(ValueError):
    """Raised when input text or parameters are invalid."""
    pass


def truncate(text: str, max_chars: int = 10000, suffix: str = "\n[... truncated due to length ...]") -> str:
    """Truncate text to a maximum number of characters."""
    if not isinstance(text, str):
        return str(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix

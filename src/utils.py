"""Utility helper functions and custom exceptions for the application."""

from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any


class InputValidationError(ValueError):
    """Raised when input text or parameters are invalid."""
    pass


class JSONParseError(ValueError):
    """Raised when parsing JSON from the LLM fails."""
    pass


def truncate(text: str, max_chars: int = 10000, suffix: str = "\n[... truncated due to length ...]") -> str:
    """Truncate text to a maximum number of characters."""
    if not isinstance(text, str):
        return str(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


def normalize_payload(payload: Any) -> Any:
    """Normalize input or output payload data structures."""
    if isinstance(payload, dict):
        return {k: normalize_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [normalize_payload(item) for item in payload]
    return payload


def parse_decimal_safe(value: Any) -> Decimal | None:
    """Safely parse numbers into Decimal objects if possible."""
    if value is None:
        return None
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None

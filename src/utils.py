"""Utility helper functions and custom exceptions for the application."""

from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any
import json
import re


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


def redact_secrets(text: str) -> str:
    """Redact sensitive information like API keys or tokens from text."""
    if not isinstance(text, str):
        return str(text)
    # Basic redaction patterns for common API keys/secrets
    text = re.sub(r'sk-[a-zA-Z0-9]{20,}', 'sk-[REDACTED]', text)
    text = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer [REDACTED]', text)
    return text


def parse_json_object(text: str) -> dict | list:
    """Safely parse a JSON string, raising JSONParseError if it fails."""
    if not isinstance(text, str):
        raise JSONParseError("Input must be a string for JSON parsing.")
    
    cleaned_text = text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    cleaned_text = cleaned_text.strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise JSONParseError(f"Failed to parse JSON: {exc}") from exc


def parse_decimal_safe(value: Any) -> Decimal | None:
    """Safely parse numbers into Decimal objects if possible."""
    if value is None:
        return None
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None

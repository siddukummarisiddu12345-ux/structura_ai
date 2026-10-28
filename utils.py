"""Small, dependency-free helpers: input checks, JSON cleanup, secret redaction."""
from __future__ import annotations

import json
import re
from typing import Any, Iterable


class InputValidationError(ValueError):
    """The user-supplied text or options are not acceptable."""


class JSONParseError(ValueError):
    """The model output could not be parsed into a JSON object."""


# Strings a model may use to say "not found". They are converted to null so that
# "unknown" is represented one way only (null), never as a fake value.
NULL_LIKE_STRINGS = frozenset(
    {"n/a", "na", "null", "none", "unknown", "not provided", "not specified",
     "not available", "-"}
)

_FENCE_RE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n?(.*?)```", re.DOTALL)
_KEY_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
)


def validate_input_text(text: object, max_chars: int) -> str:
    """Return cleaned input text, or raise InputValidationError."""
    if not isinstance(text, str):
        raise InputValidationError("Input must be text.")
    cleaned = text.replace("\x00", "").strip()
    if not cleaned:
        raise InputValidationError("Please paste or load some document text first.")
    if len(cleaned) > max_chars:
        raise InputValidationError(
            f"Input is too long ({len(cleaned):,} characters). "
            f"The limit is {max_chars:,} characters."
        )
    return cleaned


def strip_code_fences(raw: str) -> str:
    """Remove a surrounding Markdown code fence (``` or ```json) if present."""
    text = raw.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def parse_json_object(raw: str | None) -> dict[str, Any]:
    """Parse model output into a dict.

    Handles Markdown fences and short text before/after the JSON object.
    Raises JSONParseError for anything else.
    """
    if raw is None or not raw.strip():
        raise JSONParseError("The model returned an empty response.")
    text = strip_code_fences(raw)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as first_error:
        start = text.find("{")
        if start == -1:
            raise JSONParseError(f"No JSON object found in the output: {first_error.msg}.") from first_error
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise JSONParseError(
                f"Malformed JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."
            ) from exc
    if not isinstance(value, dict):
        raise JSONParseError(f"Expected a JSON object but got {type(value).__name__}.")
    return value


def normalize_payload(value: Any, _inside_dict: bool = False) -> Any:
    """Strip whitespace from strings and turn 'N/A'-style placeholders into null.

    Placeholder conversion only applies to object values. Empty strings are left
    alone on purpose so schema validation can reject them (null means unknown).
    """
    if isinstance(value, dict):
        return {key: normalize_payload(item, True) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_payload(item, False) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if _inside_dict and stripped.lower() in NULL_LIKE_STRINGS:
            return None
        return stripped
    return value


def redact_secrets(message: str, secrets: Iterable[str] = ()) -> str:
    """Replace known secret values and common API-key shapes with [REDACTED]."""
    for secret in secrets:
        if secret and len(secret) >= 4:
            message = message.replace(secret, "[REDACTED]")
    for pattern in _KEY_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


def truncate(text: str, limit: int = 1500) -> str:
    """Shorten text for inclusion in prompts or messages."""
    return text if len(text) <= limit else text[:limit] + "... [truncated]"

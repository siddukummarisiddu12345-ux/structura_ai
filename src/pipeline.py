"""Provider-independent extraction workflow.

prompt -> provider -> parse JSON -> normalize -> validate with Pydantic
          ^----------- limited retry on output-format failures ------------|

Output is only ever marked valid when it passes the schema.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from pydantic import ValidationError

from .config import DEFAULT_MAX_INPUT_CHARS, DEFAULT_MAX_RETRIES
from .prompts import build_extraction_prompt, build_retry_prompt, build_system_prompt
from .providers.base import LLMProvider, ProviderError
from .schemas import get_template
from .utils import (
    InputValidationError,
    JSONParseError,
    normalize_payload,
    parse_json_object,
    redact_secrets,
    validate_input_text,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Outcome of one extraction request."""

    is_valid: bool
    data: dict[str, Any] | None = None
    raw_output: str | None = None
    errors: list[str] = field(default_factory=list)
    attempts: int = 0
    error_kind: str | None = None  # input | invalid_output | provider_* | None

    @property
    def json_text(self) -> str:
        """Pretty JSON for display/download (empty string if there is no data)."""
        if self.data is None:
            return ""
        return json.dumps(self.data, indent=2, ensure_ascii=False)

    @classmethod
    def failure(cls, kind: str, message: str, attempts: int = 0,
                raw_output: str | None = None) -> "ExtractionResult":
        """Build an invalid result carrying a single error message."""
        return cls(is_valid=False, errors=[message], attempts=attempts,
                   raw_output=raw_output, error_kind=kind)


def format_validation_errors(exc: ValidationError) -> list[str]:
    """Turn a Pydantic error into short 'field: message' lines (no input echo)."""
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"{location}: {error['msg']}")
    return lines


def extract(
    text: str,
    template_key: str,
    provider: LLMProvider,
    model: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    secrets: Iterable[str] = (),
) -> ExtractionResult:
    """Extract structured data from ``text`` using any LLMProvider.

    Only output-format problems (bad JSON, schema violations) are retried, at
    most ``max_retries`` extra times. Auth, quota, and network errors are
    reported immediately.
    """
    secret_list = list(secrets)
    try:
        cleaned = validate_input_text(text, max_input_chars)
        template = get_template(template_key)
    except (InputValidationError, KeyError) as exc:
        message = exc.args[0] if isinstance(exc, KeyError) else str(exc)
        return ExtractionResult.failure("input", str(message))

    system_prompt = build_system_prompt()
    user_prompt = build_extraction_prompt(template_key, cleaned)
    raw_output: str | None = None
    problems: list[str] = []
    total_attempts = max(0, max_retries) + 1

    for attempt in range(1, total_attempts + 1):
        try:
            raw_output = provider.generate(system_prompt, user_prompt, model)
        except ProviderError as exc:
            logger.warning("Provider call failed (%s) on attempt %d", exc.kind, attempt)
            return ExtractionResult.failure(
                exc.kind, redact_secrets(str(exc), secret_list), attempts=attempt
            )

        try:
            payload = normalize_payload(parse_json_object(raw_output))
            validated = template.schema.model_validate(payload)
        except JSONParseError as exc:
            problems = [str(exc)]
        except ValidationError as exc:
            problems = format_validation_errors(exc)
        else:
            return ExtractionResult(
                is_valid=True,
                data=validated.model_dump(mode="json"),
                raw_output=raw_output,
                attempts=attempt,
            )

        logger.info("Attempt %d produced invalid output (%d problem(s))", attempt, len(problems))
        if attempt < total_attempts:
            user_prompt = build_retry_prompt(
                template_key, cleaned, raw_output, "; ".join(problems[:10])
            )

    return ExtractionResult(
        is_valid=False,
        data=None,
        raw_output=raw_output,
        errors=problems,
        attempts=total_attempts,
        error_kind="invalid_output",
    )
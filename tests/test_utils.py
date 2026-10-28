"""Tests for the dependency-free helpers in src/utils.py."""
import pytest

from src.utils import (
    InputValidationError,
    JSONParseError,
    normalize_payload,
    parse_json_object,
    redact_secrets,
    strip_code_fences,
    truncate,
    validate_input_text,
)


def test_strip_code_fences_json_block():
    assert strip_code_fences('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_plain_block():
    assert strip_code_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_code_fences_no_fence_is_unchanged():
    assert strip_code_fences('  {"a": 1}  ') == '{"a": 1}'


def test_parse_plain_json():
    assert parse_json_object('{"a": 1, "b": null}') == {"a": 1, "b": None}


def test_parse_json_inside_markdown_fence():
    assert parse_json_object('```json\n{"name": "Ada"}\n```') == {"name": "Ada"}


def test_parse_json_with_surrounding_prose():
    raw = 'Here is the result: {"name": "Ada"} Hope that helps!'
    assert parse_json_object(raw) == {"name": "Ada"}


@pytest.mark.parametrize("raw", ['{"a": 1,', "not json at all", '{"a": }'])
def test_parse_malformed_json_raises(raw):
    with pytest.raises(JSONParseError):
        parse_json_object(raw)


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_parse_empty_output_raises(raw):
    with pytest.raises(JSONParseError):
        parse_json_object(raw)


def test_parse_non_object_json_raises():
    with pytest.raises(JSONParseError):
        parse_json_object("[1, 2, 3]")


def test_validate_input_text_strips_and_returns():
    assert validate_input_text("  hello  ", 100) == "hello"


def test_validate_input_text_removes_null_bytes():
    assert validate_input_text("he\x00llo", 100) == "hello"


@pytest.mark.parametrize("value", ["", "   \n", None, 123])
def test_validate_input_text_rejects_empty_or_wrong_type(value):
    with pytest.raises(InputValidationError):
        validate_input_text(value, 100)


def test_validate_input_text_rejects_too_long():
    with pytest.raises(InputValidationError):
        validate_input_text("x" * 101, 100)


def test_normalize_payload_turns_placeholders_into_null():
    result = normalize_payload({"vendor": " N/A ", "total": "unknown", "name": "  Ada  "})
    assert result == {"vendor": None, "total": None, "name": "Ada"}


def test_normalize_payload_keeps_empty_string_so_validation_can_reject_it():
    assert normalize_payload({"vendor": ""}) == {"vendor": ""}


def test_normalize_payload_handles_nested_values():
    result = normalize_payload({"skills": [" Python ", "SQL"], "job": {"title": "none"}})
    assert result == {"skills": ["Python", "SQL"], "job": {"title": None}}


def test_redact_secrets_known_value():
    assert redact_secrets("failed with key abc123SECRET", ["abc123SECRET"]) == "failed with key [REDACTED]"


def test_redact_secrets_common_key_shapes():
    text = "keys: AIzaSyA1234567890abcdefghijklmnop and sk-abcdefghijklmnop1234"
    cleaned = redact_secrets(text)
    assert "AIza" not in cleaned and "sk-abc" not in cleaned


def test_truncate():
    assert truncate("abc", 10) == "abc"
    assert truncate("a" * 20, 5).startswith("aaaaa") and "truncated" in truncate("a" * 20, 5)
"""Tests for the GPT client utility helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from hier_config_gpt.clients.utils import (
    coerce_content_to_text,
    extract_first_list,
    parse_plan_commands,
    parse_plan_payload,
    retry_with_backoff,
)


def test_coerce_content_to_text_none() -> None:
    assert not coerce_content_to_text(None)


def test_coerce_content_to_text_string() -> None:
    assert coerce_content_to_text("hello") == "hello"


def test_coerce_content_to_text_iterable() -> None:
    content = [
        "a",
        SimpleNamespace(text="b"),
        {"text": "c"},
        {"other": "ignored"},
        SimpleNamespace(other="ignored"),
    ]

    assert coerce_content_to_text(content) == "abc"


def test_coerce_content_to_text_non_iterable() -> None:
    assert coerce_content_to_text(5) == "5"


def test_parse_plan_payload_json_object() -> None:
    assert parse_plan_payload('{"plan": ["a", "b"]}') == {"plan": ["a", "b"]}


def test_parse_plan_payload_json_list() -> None:
    assert parse_plan_payload('["a", "b"]') == {"plan": ["a", "b"]}


def test_parse_plan_payload_embedded_list() -> None:
    assert parse_plan_payload('Here is a plan: ["a", "b"] done') == {"plan": ["a", "b"]}


def test_parse_plan_payload_empty() -> None:
    with pytest.raises(ValueError, match="Empty response payload from provider"):
        parse_plan_payload("   ")


def test_parse_plan_payload_scalar() -> None:
    with pytest.raises(TypeError, match="Provider JSON payload must be an object"):
        parse_plan_payload('"just a string"')


def test_parse_plan_payload_missing_plan() -> None:
    with pytest.raises(ValueError, match="must include a 'plan' field"):
        parse_plan_payload('{"other": 1}')


def test_parse_plan_payload_no_list_found() -> None:
    with pytest.raises(ValueError, match="No JSON list found in payload"):
        parse_plan_payload("no json here")


def test_parse_plan_payload_invalid_embedded_list() -> None:
    with pytest.raises(ValueError, match="Provider did not return valid JSON"):
        parse_plan_payload("text [not, valid, json] text")


def test_parse_plan_commands() -> None:
    assert parse_plan_commands('{"plan": ["a", 1]}') == ["a", "1"]


def test_parse_plan_commands_non_list_plan() -> None:
    with pytest.raises(TypeError, match="must be a list of commands"):
        parse_plan_commands('{"plan": "not a list"}')


def test_extract_first_list() -> None:
    assert extract_first_list('junk ["a"] junk') == '["a"]'


def test_extract_first_list_missing() -> None:
    with pytest.raises(ValueError, match="No JSON list found in payload"):
        extract_first_list("junk")


def test_retry_with_backoff_success() -> None:
    assert retry_with_backoff(lambda: "ok") == "ok"


def test_retry_with_backoff_recovers() -> None:
    attempts: list[int] = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            msg = "transient failure"
            raise RuntimeError(msg)
        return "recovered"

    with patch("hier_config_gpt.clients.utils.time.sleep") as mock_sleep:
        result = retry_with_backoff(flaky, retries=2, backoff_seconds=0.1)

    assert result == "recovered"
    assert len(attempts) == 2
    mock_sleep.assert_called_once_with(0.1)


def test_retry_with_backoff_exhausted() -> None:
    def always_fails() -> str:
        msg = "permanent failure"
        raise RuntimeError(msg)

    with (
        patch("hier_config_gpt.clients.utils.time.sleep") as mock_sleep,
        pytest.raises(RuntimeError, match="permanent failure"),
    ):
        retry_with_backoff(always_fails, retries=2, backoff_seconds=0.5)

    # Exponential backoff: 0.5s then 1.0s.
    assert [call.args[0] for call in mock_sleep.call_args_list] == [0.5, 1.0]

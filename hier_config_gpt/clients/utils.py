"""Utility helpers for GPT clients."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def _extract_item_text(item: object) -> str | None:
    """Extract a text fragment from a provider content item."""
    if isinstance(item, str):
        return item

    text = (
        cast("dict[str, object]", item).get("text")
        if isinstance(item, dict)
        else getattr(item, "text", None)
    )

    return None if text is None else str(text)


def coerce_content_to_text(content: object) -> str:
    """Flatten provider-specific content payloads into a single string."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, Iterable):
        items = cast("Iterable[object]", content)
        return "".join(
            text for text in (_extract_item_text(item) for item in items) if text
        )

    return str(content)


def _load_json_payload(text_payload: str) -> object:
    """Load a JSON document from text, falling back to the first embedded list."""
    try:
        return cast("object", json.loads(text_payload))
    except json.JSONDecodeError as exc:
        plan_text = extract_first_list(text_payload)
        try:
            return cast("object", json.loads(plan_text))
        except json.JSONDecodeError:
            msg = "Provider did not return valid JSON."
            raise ValueError(msg) from exc


def parse_plan_payload(raw_payload: object) -> dict[str, object]:
    """Parse a JSON payload expected to contain a remediation plan."""
    text_payload = coerce_content_to_text(raw_payload).strip()
    if not text_payload:
        msg = "Empty response payload from provider."
        raise ValueError(msg)

    parsed = _load_json_payload(text_payload)

    if isinstance(parsed, list):
        parsed = {"plan": cast("list[object]", parsed)}
    elif not isinstance(parsed, dict):
        msg = "Provider JSON payload must be an object."
        raise TypeError(msg)

    payload = cast("dict[str, object]", parsed)
    if "plan" not in payload:
        msg = "Provider JSON payload must include a 'plan' field."
        raise ValueError(msg)

    return payload


def parse_plan_commands(raw_payload: object) -> list[str]:
    """Parse a provider payload and return the remediation plan commands."""
    payload = parse_plan_payload(raw_payload)
    plan = payload["plan"]
    if not isinstance(plan, list):
        msg = "Provider 'plan' field must be a list of commands."
        raise TypeError(msg)

    return [str(command) for command in cast("list[object]", plan)]


def extract_first_list(text: str) -> str:
    """Extract the first JSON-like list from text or raise an error."""
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        msg = "No JSON list found in payload."
        raise ValueError(msg)

    return match.group(0)


def retry_with_backoff(
    func: Callable[[], _T],
    *,
    retries: int = 2,
    backoff_seconds: float = 0.5,
) -> _T:
    """Execute a function with retry and exponential backoff."""
    try:
        result = func()
    # A generic retry helper must catch any provider error.
    except Exception:  # pylint: disable=broad-exception-caught
        if retries <= 0:
            logger.exception("Provider call failed after retries")
            raise

        logger.warning(
            "Provider call failed, retrying in %.2fs (%d retries left)",
            backoff_seconds,
            retries,
        )
        time.sleep(backoff_seconds)
        return retry_with_backoff(
            func,
            retries=retries - 1,
            backoff_seconds=backoff_seconds * 2,
        )

    return result

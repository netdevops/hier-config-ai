"""Utility helpers for GPT clients."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any


logger = logging.getLogger(__name__)


def coerce_content_to_text(content: Any) -> str:
    """Flatten provider-specific content payloads into a single string."""

    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, Iterable):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue

            text = None
            if hasattr(item, "text"):
                text = getattr(item, "text")
            elif isinstance(item, dict):
                text = item.get("text")

            if text is not None:
                parts.append(str(text))

        return "".join(parts)

    return str(content)


def parse_plan_payload(raw_payload: Any) -> dict[str, Any]:
    """Parse a JSON payload expected to contain a remediation plan."""

    text_payload = coerce_content_to_text(raw_payload).strip()
    if not text_payload:
        raise ValueError("Empty response payload from provider.")

    try:
        parsed = json.loads(text_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("Provider did not return valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Provider JSON payload must be an object.")

    if "plan" not in parsed:
        raise ValueError("Provider JSON payload must include a 'plan' field.")

    return parsed


def retry_with_backoff(
    func: Callable[[], Any],
    *,
    retries: int = 2,
    backoff_seconds: float = 0.5,
) -> Any:
    """Execute a function with retry and exponential backoff."""

    attempt = 0
    while True:
        try:
            return func()
        except Exception as exc:  # pragma: no cover - defensive logging
            attempt += 1
            if attempt > retries:
                logger.exception("Provider call failed after retries: %s", exc)
                raise

            sleep_for = backoff_seconds * (2 ** (attempt - 1))
            logger.warning("Provider call failed (attempt %s/%s), retrying in %.2fs", attempt, retries, sleep_for)
            time.sleep(sleep_for)

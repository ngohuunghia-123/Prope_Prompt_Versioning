"""Controlled projection of retained call bodies and telemetry into UI-safe detail."""

import json
import re
from collections.abc import Mapping
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

__all__ = [
    "RESOLVE_BUCKETS",
    "SEARCH_BUCKETS",
    "redacted_messages",
    "resolve_duration_seconds",
    "unapproved_pointer_rows",
    "resolve_miss_total",
    "revision_conflict_total",
    "revision_created_total",
    "search_duration_seconds",
    "unfiltered_query_total",
]

RESOLVE_BUCKETS = (0.0005, 0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, float("inf"))
SEARCH_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, float("inf"))

resolve_duration_seconds = Histogram(
    "prope_registry_resolve_duration_seconds",
    "Wall time for one model-name resolution, by outcome.",
    labelnames=("outcome",),
    buckets=RESOLVE_BUCKETS,
)
resolve_miss_total = Counter(
    "prope_registry_resolve_miss_total",
    "Resolutions that returned no binding, by miss reason.",
    labelnames=("reason",),
)
search_duration_seconds = Histogram(
    "prope_registry_search_duration_seconds",
    "Wall time for one list-and-search query, by keyword presence.",
    labelnames=("keyword",),
    buckets=SEARCH_BUCKETS,
)
revision_created_total = Counter(
    "prope_registry_revision_created_total",
    "Revisions written.",
)
revision_conflict_total = Counter(
    "prope_registry_revision_conflict_total",
    "Concurrent revision-number conflicts.",
)
unfiltered_query_total = Counter(
    "prope_registry_unfiltered_query_total",
    "Reads issued through the unsafe unfiltered path.",
)
unapproved_pointer_rows = Gauge(
    "prope_registry_unapproved_pointer_rows",
    "Released pointers naming a revision that is not approved.",
)

SENSITIVE_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "password", "secret", "token", "access_token"}
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)")
REDACTED = "[REDACTED]"


def _redact_text(value: str) -> tuple[str, bool]:
    result = EMAIL.sub(REDACTED, value)
    result = BEARER.sub(REDACTED, result)
    result = PHONE.sub(REDACTED, result)
    return result, result != value


def _redact(value: Any, *, key: str | None = None) -> tuple[Any, bool]:
    if key is not None and key.casefold() in SENSITIVE_KEYS:
        return REDACTED, True
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        redacted = False
        items = []
        for item in value:
            next_item, changed = _redact(item)
            items.append(next_item)
            redacted = redacted or changed
        return items, redacted
    if isinstance(value, Mapping):
        redacted = False
        result: dict[str, Any] = {}
        for item_key, item_value in value.items():
            next_value, changed = _redact(item_value, key=str(item_key))
            result[str(item_key)] = next_value
            redacted = redacted or changed
        return result, redacted
    return value, False


def _content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def redacted_messages(request_body: str | None, response_body: str | None) -> list[dict[str, Any]]:
    """Return chatbot messages without allowing malformed JSON to bypass redaction."""
    messages: list[dict[str, Any]] = []
    if request_body:
        payload = json.loads(request_body)
        request_messages = payload.get("messages", []) if isinstance(payload, dict) else []
        if not isinstance(request_messages, list):
            raise ValueError("request messages are not a list")
        for index, message in enumerate(request_messages):
            if not isinstance(message, dict):
                raise ValueError("request message is not an object")
            role = str(message.get("role", "user"))
            if role not in {"system", "user", "assistant", "tool"}:
                role = "user"
            safe, changed = _redact(message.get("content", ""))
            messages.append(
                {
                    "message_id": f"request-{index}",
                    "role": role,
                    "content": _content(safe),
                    "redacted": changed,
                }
            )
    if response_body:
        try:
            parsed: Any = json.loads(response_body)
        except json.JSONDecodeError:
            parsed = response_body
        safe, changed = _redact(parsed)
        messages.append(
            {
                "message_id": "response",
                "role": "assistant",
                "content": _content(safe),
                "redacted": changed,
            }
        )
    return messages

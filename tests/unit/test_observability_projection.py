from datetime import UTC, datetime
from decimal import Decimal

import pytest

from prope.call_ledger.seams import CallRecordListing
from prope.prompt_registry.api import _call_trace
from prope.prompt_registry.observability import redacted_messages


def _record(**overrides: object) -> CallRecordListing:
    values: dict[str, object] = {
        "call_id": "cal_trace",
        "source": "gateway",
        "version_id": "rev_trace",
        "revision_number": 4,
        "consumer_key_id": None,
        "provider_config_id": "pvc_trace",
        "upstream_model": "model-trace",
        "outcome": "ok",
        "pinned": False,
        "fallback": False,
        "streaming": False,
        "input_tokens": 12,
        "output_tokens": 7,
        "usage_status": "reported",
        "cost": Decimal("0.0100"),
        "currency": "USD",
        "cost_status": "priced",
        "added_latency_ms": 20,
        "upstream_duration_ms": 80,
        "error_class": None,
        "created_at": datetime(2026, 8, 20, tzinfo=UTC),
    }
    values.update(overrides)
    return CallRecordListing(**values)  # type: ignore[arg-type]


def test_call_trace_uses_only_recorded_latency() -> None:
    duration, spans = _call_trace(_record())
    assert duration == 100
    assert [(span.name, span.duration_ms) for span in spans] == [
        ("gateway.request", 100),
        ("prope.overhead", 20),
        ("provider.generation", 80),
    ]


def test_historical_call_does_not_invent_spans() -> None:
    duration, spans = _call_trace(_record(added_latency_ms=None, upstream_duration_ms=None))
    assert duration is None
    assert [(span.name, span.duration_ms) for span in spans] == [("gateway.request", None)]


def test_request_projection_redacts_sensitive_values() -> None:
    messages = redacted_messages(
        '{"messages":[{"role":"user","content":"email me at person@example.com"}],"api_key":"secret"}',
        '{"answer":"call +84 912 345 678"}',
    )
    assert all("person@example.com" not in message["content"] for message in messages)
    assert all("912 345 678" not in message["content"] for message in messages)
    assert any(message["redacted"] for message in messages)


def test_malformed_request_fails_closed() -> None:
    with pytest.raises(ValueError):
        redacted_messages("not-json", "response")

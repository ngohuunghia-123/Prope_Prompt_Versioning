"""A-087: the call record is handed to call-ledger after the response is flushed.

The gateway generates the ``call_id`` at request time (A-099) and owns nothing
else about the record. ``enqueue`` never raises (INT-018), and the timing span
here starts after the flush so it is excluded from the added-latency figure by
construction rather than by subtraction.
"""

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from ulid import ULID

from prope.call_ledger.domain import CallBodyDraft, CallRecordDraft, Outcome, Source
from prope.call_ledger.enqueue import enqueue
from prope.gateway.domain import CALL_ID_PREFIX
from prope.gateway.observability import (
    call_total,
    enqueue_duration_seconds,
    pinned_call_total,
    record_missing_version_id_total,
)

log = structlog.get_logger(__name__)

__all__ = ["CallFacts", "new_call_id", "record_call", "serialise"]


def new_call_id() -> str:
    return f"{CALL_ID_PREFIX}{ULID()}"


def serialise(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return None


@dataclass(slots=True)
class CallFacts:
    call_id: str
    workspace_id: str
    consumer_key_id: str
    created_at: datetime
    outcome: Outcome
    model_name: str
    streaming: bool = False
    pinned: bool = False
    fallback: bool = False
    prompt_id: str | None = None
    version_id: str | None = None
    revision_number: int | None = None
    provider_config_id: str | None = None
    upstream_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    added_latency_ms: int | None = None
    upstream_duration_ms: int | None = None
    error_class: str | None = None
    request_body: str | None = None
    response_body: str | None = None

    def draft(self) -> CallRecordDraft:
        body = CallBodyDraft(request_body=self.request_body, response_body=self.response_body)
        return CallRecordDraft(
            call_id=self.call_id,
            workspace_id=self.workspace_id,
            source=Source.GATEWAY,
            outcome=self.outcome,
            created_at=self.created_at,
            prompt_id=self.prompt_id,
            version_id=self.version_id,
            revision_number=self.revision_number,
            consumer_key_id=self.consumer_key_id,
            provider_config_id=self.provider_config_id,
            upstream_model=self.upstream_model,
            pinned=self.pinned,
            fallback=self.fallback,
            streaming=self.streaming,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            added_latency_ms=self.added_latency_ms,
            upstream_duration_ms=self.upstream_duration_ms,
            error_class=self.error_class,
            body=body,
        )


def caller_request_body(
    messages: Sequence[Mapping[str, Any]], variables: Mapping[str, Any] | None
) -> str | None:
    return serialise({"messages": list(messages), "variables": dict(variables or {})})


def record_call(facts: CallFacts) -> None:
    started = time.perf_counter()

    call_total.labels(outcome=facts.outcome.value).inc()
    if facts.pinned:
        pinned_call_total.labels(prompt=facts.model_name).inc()

    if facts.version_id is None:
        record_missing_version_id_total.inc()
        log.warning(
            "gateway.record_without_version_id",
            call_id=facts.call_id,
            workspace_id=facts.workspace_id,
            reason="no_version_id",
        )
        enqueue_duration_seconds.observe(time.perf_counter() - started)
        return

    try:
        enqueue(facts.draft())
    except Exception as error:
        log.warning(
            "gateway.record_abandoned",
            call_id=facts.call_id,
            workspace_id=facts.workspace_id,
            reason=type(error).__name__,
        )
    finally:
        enqueue_duration_seconds.observe(time.perf_counter() - started)

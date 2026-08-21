"""A-143: at most 20 in-flight chat completions per consumer key, per process.

Never queued, never delayed, never retried on the caller's behalf (A-084). The
refusal is immediate and the counter is bucketed rather than keyed on the raw
key id, because ADR-0030 forbids an unbounded metric label.
"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager

from prope.gateway.observability import admission_refused_total, in_flight

__all__ = [
    "KEY_ID_BUCKETS",
    "MAX_IN_FLIGHT_PER_KEY",
    "AdmissionRefused",
    "admit",
    "key_id_bucket",
    "reset_admission",
]

MAX_IN_FLIGHT_PER_KEY = 20

KEY_ID_BUCKETS = 16


class AdmissionRefused(Exception):  # noqa: N818 - a refusal, not a failure
    def __init__(self, key_id: str, cap: int) -> None:
        super().__init__(f"{cap} calls are already in flight for this key")
        self.key_id = key_id
        self.cap = cap


_in_flight: dict[str, int] = {}


def key_id_bucket(key_id: str) -> str:
    digest = hashlib.sha256(key_id.encode("utf-8")).digest()
    return f"{digest[0] % KEY_ID_BUCKETS:02d}"


@contextmanager
def admit(key_id: str, cap: int = MAX_IN_FLIGHT_PER_KEY) -> Iterator[None]:
    held = _in_flight.get(key_id, 0)
    if held >= cap:
        admission_refused_total.labels(key_id_bucket=key_id_bucket(key_id)).inc()
        raise AdmissionRefused(key_id, cap)

    _in_flight[key_id] = held + 1
    in_flight.inc()
    try:
        yield
    finally:
        remaining = _in_flight.get(key_id, 1) - 1
        if remaining <= 0:
            _in_flight.pop(key_id, None)
        else:
            _in_flight[key_id] = remaining
        in_flight.dec()


def reset_admission() -> None:
    _in_flight.clear()
    in_flight.set(0)

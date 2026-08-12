"""A-143 and T-013 — 20 in flight per consumer key, refused rather than queued.

The behaviour through the route is asserted in
`tests/security/test_gateway_key_scope.py`'s neighbour; what is asserted here is
the structure, because three of its properties are invisible from outside a
single request: the cap is per KEY rather than global, a slot is returned however
the request ends, and the counter carries a BUCKET rather than the key id.

**Per process, and stated rather than discovered.** A-143 records that an A-130
gateway split makes the effective cap 40, which is the same footnote the login
limiter carries. These tests assert per-process semantics and nothing wider.
"""

import pytest
from prometheus_client import REGISTRY

from prope.gateway.admission import (
    KEY_ID_BUCKETS,
    MAX_IN_FLIGHT_PER_KEY,
    AdmissionRefused,
    admit,
    key_id_bucket,
    reset_admission,
)

KEY_A = "key_01J000000000000000000KEY1"

KEY_B = "key_01J000000000000000000KEY2"


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_admission()
    yield
    reset_admission()


def _in_flight() -> float:
    return REGISTRY.get_sample_value("prope_gateway_inflight") or 0.0


def _refused(bucket: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "prope_gateway_admission_refused_total", {"key_id_bucket": bucket}
        )
        or 0.0
    )


def test_the_declared_cap_is_the_shipped_cap() -> None:
    assert MAX_IN_FLIGHT_PER_KEY == 20


def test_the_twentieth_call_is_admitted_and_the_twenty_first_is_not() -> None:
    """The boundary on both sides, because a cap asserted only from above is a
    cap that could be off by one in the direction that refuses real traffic."""
    held = [admit(KEY_A) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()

    assert _in_flight() == MAX_IN_FLIGHT_PER_KEY

    with pytest.raises(AdmissionRefused):
        with admit(KEY_A):
            pass

    for slot in held:
        slot.__exit__(None, None, None)


def test_one_key_at_its_cap_does_not_affect_another() -> None:
    """The whole point of A-143: a misbehaving key is refused, the counter names
    its bucket, and everyone else is served. A global cap would convert one
    consumer's retry loop into the shared outage the control exists to prevent.
    """
    held = [admit(KEY_A) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()

    with admit(KEY_B):
        pass

    for slot in held:
        slot.__exit__(None, None, None)


def test_a_slot_is_returned_when_the_request_raises() -> None:
    """A gateway request can end with a refusal, an upstream error or an
    exception, and a slot leaked on any of those paths would walk a key to a
    permanent 429 that a restart is the only fix for."""
    for _ in range(MAX_IN_FLIGHT_PER_KEY + 5):
        with pytest.raises(RuntimeError):
            with admit(KEY_A):
                raise RuntimeError("the request failed")

    assert _in_flight() == 0.0
    with admit(KEY_A):
        pass


def test_a_refusal_counts_a_bucket_and_never_the_key_id() -> None:
    """ADR-0030 bounds label cardinality, and a `key_id` label on the one
    internet-facing route is unbounded by definition — a leaked key that is being
    hammered would mint a new series rather than raising an existing one."""
    bucket = key_id_bucket(KEY_A)
    before = _refused(bucket)

    held = [admit(KEY_A) for _ in range(MAX_IN_FLIGHT_PER_KEY)]
    for slot in held:
        slot.__enter__()
    with pytest.raises(AdmissionRefused):
        with admit(KEY_A):
            pass
    for slot in held:
        slot.__exit__(None, None, None)

    assert _refused(bucket) == before + 1
    assert KEY_A not in bucket
    assert int(bucket) < KEY_ID_BUCKETS


def test_the_bucket_is_stable_and_bounded() -> None:
    assert key_id_bucket(KEY_A) == key_id_bucket(KEY_A)
    buckets = {key_id_bucket(f"key_{index:026d}") for index in range(400)}
    assert len(buckets) <= KEY_ID_BUCKETS


def test_the_gauge_returns_to_zero() -> None:
    """`prope_gateway_inflight` is a gauge rather than a counter because it is a
    LEVEL, and a level that never comes back down is a level nobody can read."""
    with admit(KEY_A):
        with admit(KEY_B):
            assert _in_flight() == 2.0

    assert _in_flight() == 0.0

"""AC-11, restated — the broker is gone, and the response does not notice.

The lock's original wording (*"the call-ledger writer is stalled and its queue is
full"*) describes a mechanism ADR-0041 deleted: there is no in-process spill file
and no local queue here to fill. The lock records the restatement itself and says
the replacement drives *"the condition that actually exists: RabbitMQ
unreachable, publisher confirms failing, ADR-0041's inline direct write taking
over"* — and that the properties asserted are unchanged and now EASIER to test,
because a broker outage can be provoked deliberately.

The properties are: the response is unchanged, every record keeps its version id,
metadata is never dropped, and only bodies are dropped in the fallback path with
a counter that matches. What is provoked here is the FIRST half — the handoff
this module hands to — because everything after `enqueue` returns belongs to
call-ledger and is asserted in its own chaos tests.
"""

import asyncio

import httpx
import pytest
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.call_ledger import enqueue as enqueue_module
from prope.call_ledger.domain import Outcome
from tests.gateway import (
    MODEL,
    VERSION_ID,
    authorization,
    enqueued_records,
    gateway_api,
    seed_released_world,
    stub_upstream,
)
from tests.integration._asgi import call
from tests.provider_access._stub import completion

CALLS = 40


@pytest.fixture
def api(app_sessionmaker: async_sessionmaker[AsyncSession]):
    with gateway_api(app_sessionmaker) as application:
        yield application


def _metadata_dropped() -> float:
    return REGISTRY.get_sample_value("prope_call_ledger_metadata_dropped_total") or 0.0


def _enqueued(outcome: str) -> float:
    return (
        REGISTRY.get_sample_value(
            "prope_call_ledger_enqueued_total", {"source": "gateway", "outcome": outcome}
        )
        or 0.0
    )


def _request() -> dict:
    return {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}


async def _serve(api, monkeypatch, count: int) -> list:  # noqa: ANN001
    with stub_upstream(monkeypatch, lambda _: httpx.Response(200, json=completion())):
        return [
            await call(
                api, "POST", "/chat/completions", json_body=_request(), headers=authorization()
            )
            for _ in range(count)
        ]


async def test_no_publisher_is_running_and_every_call_is_served(
    api, migrate_engine, monkeypatch
) -> None:
    """The condition itself: nothing is draining the handoff, which is what a
    broker outage looks like from inside this module.

    A gateway that awaited a confirm — or a write — would fail every one of these
    requests. It hands the record over and returns, which is the whole of A-087
    and the reason call-ledger is a `soft` dependency and `/readyz` does not
    consider it.
    """
    await seed_released_world(migrate_engine)

    responses = await _serve(api, monkeypatch, CALLS)

    assert [response.status_code for response in responses] == [200] * CALLS


async def test_every_record_retains_its_version_id(api, migrate_engine, monkeypatch) -> None:
    """The accountability claim, under the condition that would break it.

    *"100% of calls record a version ID"* cannot tolerate loss, which is why
    ADR-0041 makes metadata durable through a second path while bodies are
    allowed to go. Here the records are still in the handoff, and each one names
    the revision that served it.
    """
    await seed_released_world(migrate_engine)

    await _serve(api, monkeypatch, CALLS)

    records = enqueued_records()
    assert len(records) == CALLS
    assert {record.version_id for record in records} == {VERSION_ID}
    assert {record.outcome for record in records} == {Outcome.OK}
    assert len({record.call_id for record in records}) == CALLS


async def test_the_call_id_is_generated_per_request_and_never_reused(
    api, migrate_engine, monkeypatch
) -> None:
    """A-099. The writer upserts on it, so two retries are two calls, two records
    and two charges — correctly — while a redelivery of one record is absorbed.
    The id is the CALLER's because the writer runs after the response and after a
    possible restart; there is no moment before the record exists at which the
    writer could have named it."""
    await seed_released_world(migrate_engine)

    await _serve(api, monkeypatch, CALLS)

    call_ids = [record.call_id for record in enqueued_records()]
    assert len(set(call_ids)) == CALLS
    assert all(call_id.startswith("cal_") for call_id in call_ids)


async def test_nothing_is_dropped_while_the_handoff_has_room(
    api, migrate_engine, monkeypatch
) -> None:
    """`prope_call_ledger_metadata_dropped_total` means *this record exists
    nowhere*. Under an ordinary broker outage with a publisher running it stays
    at zero because ADR-0041's fallback writes it; here it stays at zero because
    the record is still buffered and 40 is well inside the 512-record bound."""
    await seed_released_world(migrate_engine)
    dropped_before = _metadata_dropped()
    accepted_before = _enqueued("accepted")

    await _serve(api, monkeypatch, CALLS)

    assert _metadata_dropped() == dropped_before
    assert _enqueued("accepted") == accepted_before + CALLS


async def test_a_full_handoff_drops_loudly_and_still_serves_the_response(
    api, migrate_engine, monkeypatch
) -> None:
    """The one place inside this module where a record is genuinely lost, and the
    property that matters is which side of the boundary the loss lands on.

    The buffer is bounded on purpose: an unbounded queue converts a broker outage
    into unbounded memory growth in the process serving the response path, and
    the envelope carries bodies — so the growth is in units of payload. A bounded
    buffer that drops loudly is a worse day than one that holds everything, and
    an unbounded one is a worse day than both, later.

    What must NOT happen is a failed request, and that is what is asserted: the
    drop is counted, and the caller is served.
    """
    await seed_released_world(migrate_engine)
    monkeypatch.setattr(enqueue_module, "_handoff", asyncio.Queue(maxsize=1))
    dropped_before = _metadata_dropped()
    refused_before = _enqueued("dropped")

    responses = await _serve(api, monkeypatch, 5)

    assert [response.status_code for response in responses] == [200] * 5
    assert _metadata_dropped() == dropped_before + 4
    assert _enqueued("dropped") == refused_before + 4


async def test_enqueue_never_raises_into_the_response_path(
    api, migrate_engine, monkeypatch
) -> None:
    """INT-018's whole contract, provoked with the failure nobody predicted.

    A `put_nowait` that raises something other than `QueueFull` is caught by
    `enqueue`'s bare handler and counted, because *"a raise here would surface
    inside the gateway's response path, which is the one outcome this module
    exists to make impossible"*. The gateway relies on that promise and this is
    the test that the reliance is safe.
    """
    await seed_released_world(migrate_engine)

    class _Hostile:
        def put_nowait(self, item) -> None:  # noqa: ANN001
            raise RuntimeError("the handoff is broken in a way nobody predicted")

    monkeypatch.setattr(enqueue_module, "handoff", lambda: _Hostile())
    dropped_before = _metadata_dropped()

    responses = await _serve(api, monkeypatch, 3)

    assert [response.status_code for response in responses] == [200] * 3
    assert _metadata_dropped() == dropped_before + 3

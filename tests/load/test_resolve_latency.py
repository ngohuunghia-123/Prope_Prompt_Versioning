"""AC-4 literally: ``resolve()`` p95 under 10 ms over 1,000 requests at 50 rps.

This is the number the product's core value rests on. Every gateway call
resolves a model name to the revision that will serve it, so this latency is on
the critical path of **every** LLM request the consuming product makes — and it
is paid before the upstream call has even started. A registry that is slow here
is a tax on every feature built on top of it.

**Marked and skipped by default**, the same shape as
``tests/load/test_fifty_rps_for_ten_minutes.py`` and for the same stated reason:
``addopts = "-m 'not load'"`` would change the default selection for the whole
suite, a deselected test is invisible in the summary, and a skipped one prints
an ``s`` with its reason under ``-rs``. Run it with
``PROPE_RUN_LOAD=1 uv run pytest -m load``.

**What is measured is the seam, not the route.** INT-009 is what the gateway
imports; the HTTP surface in front of it belongs to a module that does not exist
yet, and measuring a route this phase invented would be measuring the test's own
scaffolding. The transaction boundary is included in the timing, because
``workspace_transaction`` issues its ``SET LOCAL app.workspace_id`` on every
call and a resolve that was fast only with the setting already in place would be
fast in no real caller.

**The pacing matters and is not decoration.** A thousand awaits back to back
would measure a warm connection under no contention and would report a number
nobody will ever see. Fifty a second is AC-4's stated condition, and it is the
rate at which the pool, the planner's cache and the index all behave the way
they will in production.

**The engine is POOLED, and the shared fixtures deliberately are not.**
``tests/conftest.py`` builds every session-scoped engine with ``NullPool``,
because an asyncpg connection is bound to the loop that opened it and those
fixtures outlive many loops. Under ``NullPool`` each ``workspace_transaction``
opens a new connection, and a new asyncpg connection performs a SCRAM-SHA-256
handshake — 4,096 pure-Python HMAC rounds, measured at roughly 150 ms. Every
sample below would be that handshake and none of it would be the resolve, so
this file builds its own engine with the default pool inside the running loop
and disposes it. The deployed process pools; measuring the other configuration
would be measuring a number no caller ever waits for.

**The honest caveat**, borrowed word for word in spirit from the SC5 run: this is
one measurement, on one developer host, executed once. A red result is a signal
to investigate. It is **never** a licence to raise the number — the threshold is
``acceptance_criteria``' and this file does not own it.
"""

import asyncio
import os
import statistics
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from prope.db.engine import build_engine, build_sessionmaker
from prope.db.session import workspace_transaction
from prope.prompt_registry import repository
from prope.prompt_registry.domain import ModelName, ResolveMiss, RevisionBinding
from tests.access_control import seed_user, seed_workspace
from tests.conftest import _role_url
from tests.prompt_registry import (
    NAME,
    NAMESPACE,
    approve,
    release,
    seed_prompt,
    seed_released_prompts,
    seed_revision,
)
from tests.unit import WORKSPACE_A

pytestmark = pytest.mark.load

REQUESTS = 1_000

RATE_PER_SECOND = 50

P95_BUDGET_SECONDS = 0.010

#: Enough neighbours that the index is doing real work rather than answering
#: from a table small enough to sequential-scan. A registry with one prompt in it
#: would meet any budget.
NEIGHBOURS = 200

RUN_LOAD = pytest.mark.skipif(
    not os.environ.get("PROPE_RUN_LOAD"),
    reason="AC-4's paced 1,000-request run. Set PROPE_RUN_LOAD=1 to include it.",
)

MODEL_NAME = ModelName.parse(f"{NAMESPACE}/{NAME}")


async def _registry_with_neighbours(migrate_engine) -> None:  # noqa: ANN001
    """One released prompt, surrounded by two hundred that are not the target."""
    await seed_workspace(migrate_engine)
    await seed_user(migrate_engine)

    await seed_prompt(migrate_engine)
    await seed_revision(migrate_engine)
    await approve(migrate_engine)
    await release(migrate_engine)

    await seed_released_prompts(migrate_engine, NEIGHBOURS)


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def _report(label: str, samples: list[float]) -> str:
    return (
        f"{label}: n={len(samples)} "
        f"p50={_percentile(samples, 0.50) * 1000:.2f}ms "
        f"p95={_percentile(samples, 0.95) * 1000:.2f}ms "
        f"p99={_percentile(samples, 0.99) * 1000:.2f}ms "
        f"max={max(samples) * 1000:.2f}ms "
        f"mean={statistics.fmean(samples) * 1000:.2f}ms"
    )


@asynccontextmanager
async def _pooled(postgres_container) -> AsyncIterator[async_sessionmaker[AsyncSession]]:  # noqa: ANN001
    """The runtime role over a pooled engine, built and disposed in this loop."""
    engine = build_engine(_role_url(postgres_container, "prope_app"))
    try:
        yield build_sessionmaker(engine)
    finally:
        await engine.dispose()


async def _resolve(
    sessionmaker: async_sessionmaker[AsyncSession], model_name: ModelName = MODEL_NAME
) -> tuple[float, object]:
    started = time.perf_counter()
    async with workspace_transaction(sessionmaker, WORKSPACE_A) as db:
        outcome = await repository.resolve(db, WORKSPACE_A, model_name)
    return time.perf_counter() - started, outcome


@RUN_LOAD
async def test_resolve_p95_stays_under_ten_milliseconds(
    migrate_engine, postgres_container
) -> None:
    """AC-4's condition and AC-4's number, with p50, p95, p99 and max all reported.

    A bare pass/fail hides drift, and drift is the interesting failure here: a
    p95 that creeps from 2 ms to 9 ms over a release is invisible to an assertion
    that only asks whether it is under 10.

    Every outcome is checked as well as timed. A resolve that started answering
    ``UNKNOWN_MODEL`` would get faster and would pass a timing assertion on its
    own — and would mean the gateway was serving nothing at all.
    """
    await _registry_with_neighbours(migrate_engine)

    samples: list[float] = []
    misses = 0

    async with _pooled(postgres_container) as sessionmaker:
        warm, _ = await _resolve(sessionmaker)
        assert warm > 0

        interval = 1 / RATE_PER_SECOND

        run_started = time.perf_counter()
        for index in range(REQUESTS):
            due = run_started + index * interval
            delay = due - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)

            elapsed, outcome = await _resolve(sessionmaker)
            samples.append(elapsed)
            if not isinstance(outcome, RevisionBinding):
                misses += 1

        elapsed_total = time.perf_counter() - run_started

    achieved = REQUESTS / elapsed_total

    report = _report("resolve", samples)
    print(f"\n{report}\n  {achieved:.1f} rps achieved over {elapsed_total:.1f}s")

    assert misses == 0, f"{misses} of {REQUESTS} resolves did not return a binding"

    assert achieved >= RATE_PER_SECOND * 0.9, (
        f"the run only achieved {achieved:.1f} rps against a target of {RATE_PER_SECOND}; "
        "the latency below was measured under the wrong condition"
    )

    p95 = _percentile(samples, 0.95)
    assert p95 < P95_BUDGET_SECONDS, f"{report} — over AC-4's {P95_BUDGET_SECONDS * 1000:.0f}ms"


@RUN_LOAD
async def test_a_miss_is_not_slower_than_a_hit(migrate_engine, postgres_container) -> None:
    """A-116 and A-081 as a **timing** claim, which is where they are usually lost.

    A key-scope refusal is required to be byte-identical to an unknown model
    name. Bytes are asserted elsewhere; this asserts the other channel. If a miss
    took reliably longer than a hit — an extra query, a fallback lookup, a
    retry — an unauthenticated caller could enumerate which model names exist in
    a workspace by timing the refusals, and every byte-level assertion in the
    suite would still pass.

    The bound is deliberately loose. Two different query plans will never be
    identical to the microsecond, and a tight bound here would flake on a busy
    host and teach everyone to ignore it. What is being ruled out is an
    order-of-magnitude tell, which is the only kind that is practically
    exploitable over a network.
    """
    await _registry_with_neighbours(migrate_engine)

    unknown = ModelName.parse("support/no-such-prompt")

    hits: list[float] = []
    misses: list[float] = []

    async with _pooled(postgres_container) as sessionmaker:
        await _resolve(sessionmaker)

        for _ in range(200):
            elapsed, outcome = await _resolve(sessionmaker)
            assert isinstance(outcome, RevisionBinding)
            hits.append(elapsed)

            elapsed, outcome = await _resolve(sessionmaker, unknown)
            misses.append(elapsed)
            assert outcome is ResolveMiss.UNKNOWN_MODEL

    print(f"\n{_report('hit ', hits)}\n{_report('miss', misses)}")

    hit_p95 = _percentile(hits, 0.95)
    miss_p95 = _percentile(misses, 0.95)

    assert miss_p95 < hit_p95 * 3, (
        f"a miss ({miss_p95 * 1000:.2f}ms p95) is far slower than a hit "
        f"({hit_p95 * 1000:.2f}ms p95); the difference is a channel that tells an "
        "unauthorised caller which model names exist"
    )
    assert miss_p95 < P95_BUDGET_SECONDS
